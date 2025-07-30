# Check Employee model relationships
print("Checking Employee model relationships...")
for rel in Employee.__mapper__.relationships:
    print(f"Relationship: {rel.key}")
    print(f"  - Direction: {rel.direction}")
    print(f"  - Backref: {rel.back_populates or rel.backref}")
    print("---")
