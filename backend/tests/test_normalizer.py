from backend.app.ingestion.normalizer import Normalizer

def test_normalize_college_code():
    assert Normalizer.normalize_college_code(" e001 ") == "E001"
    assert Normalizer.normalize_college_code("E157.") == "E157"
    assert Normalizer.normalize_college_code("E-205") == "E205"

def test_normalize_college_name_preserves_acronyms():
    norm, orig = Normalizer.normalize_college_name("r.v. college of engineering")
    assert "R.V." in norm or "RV" in norm
    assert orig == "r.v. college of engineering"

    norm_bms, _ = Normalizer.normalize_college_name("B.M.S. COLLEGE OF ENGINEERING")
    assert "B.M.S." in norm_bms or "BMS" in norm_bms
    assert "College" in norm_bms

def test_normalize_branch_code_and_name():
    assert Normalizer.normalize_branch_code(" cs ") == "CS"
    assert Normalizer.normalize_branch_code("AIF-") == "AIF"

    name, orig = Normalizer.normalize_branch_name("Electronics & Communicat- ion Engineering")
    assert "Communication" in name
    assert orig == "Electronics & Communicat- ion Engineering"

def test_normalize_category_code():
    assert Normalizer.normalize_category_code(" general ") == "GM"
    assert Normalizer.normalize_category_code("gm") == "GM"
    assert Normalizer.normalize_category_code("kkr") == "KKR"

def test_normalize_round():
    code, name, num = Normalizer.normalize_round("Round 1", 2026)
    assert code == "R1"
    assert num == 1

    m_code, m_name, m_num = Normalizer.normalize_round("Mock Allotment", 2026)
    assert m_code == "MOCK"
    assert m_num == 0
