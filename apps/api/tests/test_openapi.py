from fastapi.testclient import TestClient

from app.main import app


def test_workspace_read_routes_are_registered() -> None:
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/workspaces/planning-periods/{planning_period_id}" in paths
    assert "/api/auth/login" in paths
    assert "/api/auth/logout" in paths
    assert "/api/auth/me" in paths
    assert "/api/planning-periods/{planning_period_id}" in paths
    assert "/api/schedule-versions/{schedule_version_id}" in paths
    assert "/api/schedule-versions/{schedule_version_id}/work-shifts" in paths
    assert "/api/schedule-versions/{schedule_version_id}/shift-segments" in paths
    assert "/api/schedule-versions/{schedule_version_id}/change-logs" in paths
    assert "/api/schedule-versions/{schedule_version_id}/optimization-runs" in paths
    assert "/api/schedule-versions/{schedule_version_id}/validate-publish" in paths
    assert "/api/schedule-versions/{schedule_version_id}/approve" in paths
    assert "/api/schedule-versions/{schedule_version_id}/publish" in paths
    assert "/api/schedule-versions/{schedule_version_id}/archive" in paths
    assert "/api/schedule-versions/{schedule_version_id}/duplicate" in paths
    assert "/api/schedule-versions/{schedule_version_id}/commands" in paths
    assert "/api/schedule-versions/{schedule_version_id}/undo" in paths
    assert "/api/schedule-versions/{schedule_version_id}/redo" in paths
    assert "/api/schedule-versions/{schedule_version_id}/proposals" in paths
    assert "/api/schedule-versions/{schedule_version_id}/proposals/generate" in paths
    assert "/api/optimization-proposals/{proposal_id}" in paths
    assert "/api/optimization-proposals/{proposal_id}/apply" in paths
    assert "/api/optimization-proposals/{proposal_id}/reject" in paths
    assert "/api/shift-segments/{shift_segment_id}/explanation" in paths
