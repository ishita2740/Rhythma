import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_dashboard_field_selection(client: AsyncClient, token_headers: dict):
    # Fetch partial dashboard fields
    response = await client.get("/api/v1/dashboard?fields=cycle,user", headers=token_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Assert requested fields are present
    assert "cycle" in data
    assert "user" in data
    
    # Assert omitted fields are not present
    assert "insights" not in data
    assert "prediction" not in data
    assert "topObservation" not in data
    assert "cycleHistory" not in data

@pytest.mark.asyncio
async def test_dashboard_full_fetch_when_no_fields_provided(client: AsyncClient, token_headers: dict):
    # Fetch without fields
    response = await client.get("/api/v1/dashboard", headers=token_headers)
    assert response.status_code == 200
    data = response.json()
    
    # Assert all fields are present
    assert "cycle" in data
    assert "user" in data
    assert "insights" in data
    assert "hasEnoughDataForInsights" in data
    assert "loggedCycleCount" in data
    assert "cycleHistory" in data
    assert "symptomFrequency" in data
