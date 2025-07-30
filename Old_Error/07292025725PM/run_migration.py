# run_migration.py
from sqlalchemy import text
from app import db
import json

def clear_existing_data():
    """Clear existing data from project_setup_json"""
    with db.engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE project_setup_json RESTART IDENTITY CASCADE"))
        conn.commit()
    print("Cleared existing data from project_setup_json")

def create_view():
    """Create the unified project view"""
    with db.engine.connect() as conn:
        # First, add the unique constraint if it doesn't exist
        conn.execute(text("""
            DO $$
            BEGIN
                -- Add unique constraint if it doesn't exist
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'project_setup_json_project_id_key'
                ) THEN
                    ALTER TABLE project_setup_json 
                    ADD CONSTRAINT project_setup_json_project_id_key 
                    UNIQUE (project_id);
                END IF;
            END
            $$;
        """))
        
        # Then create or replace the view
        conn.execute(text("""
        DROP VIEW IF EXISTS vw_project_complete;
        CREATE VIEW vw_project_complete AS
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
        print("Created vw_project_complete view")

def migrate_project(project_id):
    """Migrate data for a single project"""
    with db.engine.connect() as conn:
        try:
            # 1. Get existing data
            setup = conn.execute(
                text("""
                    SELECT * FROM project_setups 
                    WHERE project_id = :project_id
                    FOR UPDATE
                """), 
                {'project_id': project_id}
            ).mappings().first()
            
            if not setup:
                print(f"Project {project_id} not found in project_setups")
                return False
            
            # 2. Transform the data
            try:
                # Get the employee_contractor_details
                emp_data = setup['employee_contractor_details']
                print(f"Original emp_data type: {type(emp_data)}")
                
                # If it's a string, try to parse it as JSON
                if isinstance(emp_data, str):
                    try:
                        emp_data = json.loads(emp_data)
                    except json.JSONDecodeError:
                        print("Warning: Could not parse employee_contractor_details as JSON")
                        emp_data = {}
                elif not isinstance(emp_data, dict):
                    emp_data = {}
                    
                print(f"Processed emp_data: {emp_data}")
                
            except Exception as e:
                print(f"Error processing employee_contractor_details: {e}")
                emp_data = {}
                
            # 3. Prepare the new data structure
            new_data = {
                "team_members": emp_data.get('team_members', []),
                "fixed_price_items": emp_data.get('fixed_price_items', []),
                "project_details": {
                    "estimating_sheet_link": setup.get('project_estimating_sheet_link', ''),
                    "as_bid_gross_margin": float(setup.get('as_bid_gross_margin', 0)) if setup.get('as_bid_gross_margin') else 0.0
                }
            }
            
            json_str = json.dumps(new_data)
            print(f"New data to be saved: {json_str}")
            
            # 4. Insert or update project_setup_json using parameter binding
            conn.execute(text("""
                INSERT INTO project_setup_json
                (project_id, json_data, created_at, updated_at)
                VALUES
                (%(project_id)s, to_jsonb(%(json_data)s::jsonb), NOW(), NOW())
                ON CONFLICT (project_id)
                DO UPDATE SET
                    json_data = EXCLUDED.json_data,
                    updated_at = NOW()
            """), {
                'project_id': project_id,
                'json_data': json_str
            })
            conn.commit()
            print(f"Successfully migrated project {project_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"Error migrating project {project_id}: {str(e)}")
            import traceback
            traceback.print_exc()
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
        total = 0
        for row in projects:
            total += 1
            if migrate_project(row[0]):
                success += 1
        
        print(f"\nMigration complete. Successfully migrated {success} of {total} projects.")

def verify_migration_details(project_id=184):
    """Verify migration results for a specific project"""
    with db.engine.connect() as conn:
        # Get sample data from the view
        result = conn.execute(text("""
            SELECT 
                project_id,
                project_name_quickbooks,
                jsonb_pretty(team_members) as team_members,
                jsonb_pretty(fixed_price_items) as fixed_price_items,
                jsonb_pretty(project_details) as project_details
            FROM vw_project_complete
            WHERE project_id = :project_id
        """), {'project_id': project_id})
        
        for row in result.mappings():
            print("\nProject Details:")
            print(f"Project ID: {row['project_id']}")
            print(f"QuickBooks Name: {row['project_name_quickbooks']}")
            
            print("\nTeam Members:")
            print(row['team_members'] or "[]")
            
            print("\nFixed Price Items:")
            print(row['fixed_price_items'] or "[]")
            
            print("\nProject Details:")
            print(row['project_details'] or "{}")

def debug_migration_issues(project_id=184):
    """Debug migration issues for a specific project"""
    with db.engine.connect() as conn:
        # Check the original data in project_setups
        print("\nChecking original data in project_setups:")
        result = conn.execute(text("""
            SELECT 
                project_id,
                project_name_quickbooks,
                employee_contractor_details
            FROM project_setups
            WHERE project_id = :project_id
        """), {'project_id': project_id})
        
        for row in result.mappings():
            print(f"\nProject ID: {row['project_id']}")
            print(f"QuickBooks Name: {row['project_name_quickbooks']}")
            print("\nOriginal employee_contractor_details:")
            print(row['employee_contractor_details'])
            
        # Check what's in project_setup_json
        print("\n\nChecking migrated data in project_setup_json:")
        result = conn.execute(text("""
            SELECT 
                project_id,
                json_data
            FROM project_setup_json
            WHERE project_id = :project_id
        """), {'project_id': project_id})
        
        for row in result.mappings():
            print("\nMigrated json_data:")
            print(row['json_data'])

if __name__ == '__main__':
    # Initialize Flask app context
    from app import app
    with app.app_context():
        try:
            print("Starting migration process...")
            
            # 1. Clear existing data
            print("\nStep 1: Clearing existing data...")
            clear_existing_data()
            
            # 2. Create/update the view
            print("\nStep 2: Creating/updating database view...")
            create_view()
            
            # 3. Run the migration
            print("\nStep 3: Running migration for all projects...")
            migrate_all_projects()
            
            # 4. Verify the migration
            print("\nStep 4: Verifying migration results...")
            verify_migration_details(184)
            
            # 5. Debug if needed
            print("\nStep 5: Running debug checks...")
            debug_migration_issues(184)
            
            print("\nMigration process completed successfully!")
            
        except Exception as e:
            print(f"\nError during migration: {str(e)}")
            import traceback
            traceback.print_exc()