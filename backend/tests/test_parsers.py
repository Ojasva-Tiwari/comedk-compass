from backend.app.ingestion.parsers.college_parser import CollegeParser
from backend.app.ingestion.parsers.cutoff_pdf_parser import CutoffPDFParser
from backend.app.core.enums import RecordStatus

SAMPLE_COLLEGE_HTML = b"""
<html>
  <body>
    <table>
      <tr>
        <th>COLLEGE CODE</th>
        <th>ENGINEERING COLLEGES</th>
        <th>LOCATION</th>
      </tr>
      <tr>
        <td>E001</td>
        <td>Acharya Institute of Technology- Soladevanahalli, Bengaluru</td>
        <td>BENGALURU</td>
      </tr>
      <tr>
        <td>E003</td>
        <td>Dr. ACS College of Engineering Kambipura -(Mysore Road), Bengaluru</td>
        <td>BENGALURU</td>
      </tr>
    </table>
  </body>
</html>
"""

def test_college_parser():
    parser = CollegeParser()
    res = parser.parse(SAMPLE_COLLEGE_HTML)
    assert res.status == RecordStatus.PARSED
    assert len(res.discovered_colleges) == 2
    assert res.discovered_colleges[0]["code"] == "E001"
    assert "Acharya Institute of Technology" in res.discovered_colleges[0]["name"]
    assert res.discovered_colleges[0]["location"] == "Bengaluru"

def test_cutoff_parser_rejects_empty_bytes():
    parser = CutoffPDFParser()
    res = parser.parse(b"not a valid pdf content")
    assert res.status == RecordStatus.REJECTED
    assert len(res.errors) > 0
