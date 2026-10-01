def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_data_health_endpoint(client):
    # Data health is protected; verify authentication works with admin key
    response = client.get("/api/v1/data-health", headers={"X-Admin-Key": "dev-admin-key"})
    assert response.status_code == 200
    data = response.json()
    assert "college_count" in data
    assert "branch_count" in data
    assert "cutoff_record_count" in data
    assert "current_ingestion_status" in data

def test_colleges_endpoint(client):
    response = client.get("/api/v1/colleges")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data

def test_branches_endpoint(client):
    response = client.get("/api/v1/branches")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data

def test_cutoffs_endpoint(client):
    response = client.get("/api/v1/cutoffs")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data

def test_seat_records_endpoint(client):
    response = client.get("/api/v1/seat-records")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data

def test_fees_endpoint(client):
    response = client.get("/api/v1/fees")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data

def test_sources_endpoint(client):
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data

def test_html_admin_data_health_page(client):
    # HTML admin data health page is protected
    response = client.get("/data-health", headers={"X-Admin-Key": "dev-admin-key"})
    assert response.status_code == 200
    assert "COMEDK Compass" in response.text
    assert "Engineering Colleges" in response.text
