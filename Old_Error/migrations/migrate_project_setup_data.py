# migrations/migrate_project_setup_data.py
import json
from sqlalchemy import text
from app import create_app, db

def create_view():
    """Create the unified project view"""
    with db.engine.connect() as conn:
        conn.execute(text("""
        CREATE OR REPLACE VIEW vw_project_complete AS
        SELECT 
            ps.*,
            COALESCE(psj.json_data->'team_members', 
                    (ps.employee_contractor_details->'team_members')::jsonb, 
                    '[]'::jsonb) as team_members,
            COALESCE(psj.json_data->'fixed_price_items',
                    (ps.employee_contractor_details->'fixed_price_items')::jsonb,
                    '[]'::jsonb) as fixed_price_items,
            COALESCE(psj.json_data->'project_details', '{}'::jsonb) as project_details
        FROM 
            project_setups ps
        LEFT JOIN 
            project_setup_json psj ON ps.project_id = psj.project_id;
        """))
        conn.commit()

def migrate_project(project_id):
    """Migrate data for a single project"""
    with db.engine.connect() as conn:
        try:
            # 1. Get existing data
            setup = conn.execute(
                text("""
                    SELECT * FROM project_setups 
                    WHERE project_id = :pid
                    FOR UPDATE
                """), 
                {'pid': project_id}
            ).mappings().first()
            
            if not setup:
                print(f"Project {project_id} not found in project_setups")
                return False
            
            # 2. Skip if already migrated
            existing = conn.execute(
                text("SELECT 1 FROM project_setup_json WHERE project_id = :pid"),
                {'pid': project_id}
            ).scalar()
            
            if existing:
                print(f"Project {project_id} already migrated")
                return True
                
            # 3. Transform the data
            try:
                emp_data = json.loads(setup['employee_contractor_details'] or '{}')
            except:
                emp_data = {}
                
            new_data = {
                "team_members": emp_data.get('team_members', []),
                "fixed_price_items": emp_data.get('fixed_price_items', []),
                "project_details": {
                    "estimating_sheet_link": setup['project_estimating_sheet_link'],
                    "as_bid_gross_margin": setup['as_bid_gross_margin']
                }
            }
            
            # 4. Insert into project_setup_json
            conn.execute(text("""
                INSERT INTO project_setup_json 
                (project_id, json_data, created_at, updated_at)
                VALUES 
                (:project_id, :json_data::jsonb, NOW(), NOW())
            """), {
                'project_id': project_id,
                'json_data': json.dumps(new_data)
            })
            
            conn.commit()
            print(f"Successfully migrated project {project_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"Error migrating project {project_id}: {str(e)}")
            return False

def migrate_all_projects():
    """Migrate all projects with valid project_id"""
    with db.engine.connect() as conn:
        # Get all projects with project_id
        projects = conn.execute(text("""
            SELECT DISTINCT project_id 
            FROM project_setups 
            WHERE project_id IS NOT NULL
        """))
        
        success = 0
        for row in projects:
            if migrate_project(row[0]):
                success += 1
        
        print(f"\nMigration complete. Successfully migrated {success} projects.")

def verify_migration(project_id):
    """Verify the migration for a project"""
    with db.engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                ps.id,
                ps.project_id,
                ps.project_name_quickbooks,
                jsonb_array_length(COALESCE(psj.json_data->'team_members', 
                                          (ps.employee_contractor_details->'team_members')::jsonb, 
                                          '[]'::jsonb)) as team_member_count,
                jsonb_array_length(COALESCE(psj.json_data->'fixed_price_items',
                                          (ps.employee_contractor_details->'fixed_price_items')::jsonb,
                                          '[]'::jsonb)) as fixed_item_count
            FROM 
                project_setups ps
            LEFT JOIN 
                project_setup_json psj ON ps.project_id = psj.project_id
            WHERE 
                ps.project_id = :pid
        """), {'pid': project_id})
        
        return result.mappings().first()

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print("Creating database view...")
        create_view()
        
        print("\nStarting migration...")
        migrate_all_projects()
        
        # Verify a sample project
        sample_id = 184  # Change to a valid project_id
        print(f"\nVerifying migration for project {sample_id}:")
        verification = verify_migration(sample_id)
        if verification:
            print("Verification Results:")
            print(f"Project ID: {verification['project_id']}")
            print(f"QuickBooks Name: {verification['project_name_quickbooks']}")
            print(f"Team Members: {verification['team_member_count']}")
            print(f"Fixed Price Items: {verification['fixed_item_count']}")
        else:
            print(f"Could not verify project {sample_id}")