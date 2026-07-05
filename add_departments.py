from database import init_db, create_department

init_db()

departments = [
    "Computer Science",
    "Information Technology",
    "Electronics",
    "Mechanical"
]

for dept in departments:
    success, result = create_department(dept)
    if success:
        print(f"  Created: {dept}")
    else:
        print(f"  Skipped: {dept} ({result})")

print("\nDepartments ready!")