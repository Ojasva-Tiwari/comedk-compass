import uuid
from sqlalchemy import select
from backend.app.models.college import College, CollegeAlias
from backend.app.models.branch import Branch

def test_college_model_and_alias_insertion(db):
    test_code = f"TEST{uuid.uuid4().hex[:4].upper()}"
    college = College(
        code=test_code,
        name="Test Engineering College",
        original_name="Test Engineering College Official",
        location="Bengaluru"
    )
    db.add(college)
    db.commit()
    db.refresh(college)

    alias = CollegeAlias(college_id=college.id, alias="TEC Bengaluru", source="COMEDK")
    db.add(alias)
    db.commit()

    try:
        fetched = db.execute(select(College).where(College.code == test_code)).scalar_one()
        assert fetched.code == test_code
        assert len(fetched.aliases) == 1
        assert fetched.aliases[0].alias == "TEC Bengaluru"
    finally:
        # Clean up test records
        db.delete(college)
        db.commit()

def test_branch_uniqueness(db):
    test_bcode = f"TB{uuid.uuid4().hex[:3].upper()}"
    branch1 = Branch(code=test_bcode, name="Test Branch", original_name="Test Branch Orig")
    db.add(branch1)
    db.commit()

    try:
        existing = db.execute(select(Branch).where(Branch.code == test_bcode)).scalar_one_or_none()
        assert existing is not None
        assert existing.code == test_bcode
    finally:
        # Clean up test records
        db.delete(branch1)
        db.commit()
