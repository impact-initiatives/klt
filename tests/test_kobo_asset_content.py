"""Tests for kobo_asset_content resource with merge disposition and child tables.

This test verifies that DLT's merge disposition with primary_key=["asset_uid"]
correctly handles child tables (unpacked nested data like survey items).

IMPORTANT: DLT's merge behavior with nested data
-----------------------------------------------
When a parent record is merged (updated) based on its primary_key:
- DLT uses _dlt_root_id to link child records to the parent
- DLT DELETES all old child records linked to that parent
- DLT INSERTS all new child records from the updated parent

This means: Child tables are REPLACED, not accumulated/merged individually.

For kobo_asset_content:
- If a form's survey changes (questions added/removed/modified)
- The child table (kobo_asset_content__survey) will reflect ONLY the current state
- Old survey items will be removed, new ones will be added
- This is the correct behavior for representing the current form structure
"""

import responses

from .conftest import (
    make_asset_content_data,
    make_asset_content_url,
    make_asset_data,
    make_drf_response,
    make_project_view_assets_url,
)


@responses.activate
def test_kobo_asset_content_merge_behavior_with_child_tables(
    kobo_pipeline, db, kobo_client
):
    """Test that merge disposition correctly handles parent and child tables.

    This test answers the question: When DLT loads kobo_asset_content with
    primary_key=["asset_uid"] and write_disposition="merge", does this get
    reflected automatically in child tables (kobo_asset_content__survey)?

    Expected behavior (CONFIRMED BY EMPIRICAL TESTING):
    1. No duplicates in parent or child tables
    2. When parent is merged, child records are REPLACED (not accumulated)
    3. No information is dropped - new content is fully loaded
    4. Old child records are deleted based on _dlt_root_id linkage

    The test scenario:
    - Run 1: Load asset_A with 3 survey questions (q1, q2, q3)
    - Run 2: Load asset_A with 2 DIFFERENT survey questions (q4, q5)
    - Verify:
      * Parent table: Still 1 record for asset_A (no duplicate)
      * Child table: Exactly 2 questions (q4, q5) - old questions GONE
      * No duplicates: q1, q2, q3 are removed (replaced, not kept)
      * No data loss: q4, q5 are fully present with correct details

    This is the CORRECT behavior for KoboToolbox forms:
    - Forms are edited over time (questions added/removed/modified)
    - The database should reflect the CURRENT state of the form
    - Historical versions are not accumulated in the same table
    """
    # Arrange: Create parent asset
    asset = make_asset_data(
        uid="asset_A",
        submission_count=3,
    )

    project_view_uid = "test_pv_merge"
    asset_api_url = make_project_view_assets_url(project_view_uid)

    # Mock asset endpoint (will be used by both runs)
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    # Arrange Run 1: Content with 3 survey questions
    content_run1 = make_asset_content_data(
        survey_items=[
            {
                "type": "text",
                "name": "question_1",
                "$kuid": "kuid_q1",
                "$xpath": "question_1",
                "$autoname": "question_1",
            },
            {
                "type": "integer",
                "name": "question_2",
                "$kuid": "kuid_q2",
                "$xpath": "question_2",
                "$autoname": "question_2",
            },
            {
                "type": "select_one",
                "name": "question_3",
                "$kuid": "kuid_q3",
                "$xpath": "question_3",
                "$autoname": "question_3",
            },
        ],
        form_title="Test Form Run 1",
    )

    content_api_url = make_asset_content_url("asset_A")

    # Mock content endpoint for first run
    responses.add(
        responses.GET,
        content_api_url,
        json={"data": [content_run1]},
        status=200,
    )

    # Create resources
    from klt.resources.kobo_asset import (
        make_resource_kobo_asset,
        make_resource_kobo_asset_content,
    )

    kobo_asset = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    kobo_asset_content = make_resource_kobo_asset_content(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset,
        parallelized=False,
    )

    # Act: Run pipeline first time
    load_info_1 = kobo_pipeline.run(
        [kobo_asset, kobo_asset_content],
        write_disposition="merge",
    )

    # Assert Run 1: Pipeline completed successfully
    assert load_info_1.has_failed_jobs is False

    # Assert Run 1: Parent table has 1 record
    parent_count_1 = db.execute("SELECT COUNT(*) FROM kobo_asset_content").fetchone()[0]
    assert parent_count_1 == 1, f"Expected 1 parent record, got {parent_count_1}"

    # Assert Run 1: Verify asset_uid is set correctly
    parent_record_1 = db.execute("SELECT asset_uid FROM kobo_asset_content").fetchone()
    assert parent_record_1[0] == "asset_A"

    # Assert Run 1: Child table has 3 survey items
    child_count_1 = db.execute(
        "SELECT COUNT(*) FROM kobo_asset_content__survey"
    ).fetchone()[0]
    assert child_count_1 == 3, f"Expected 3 survey items, got {child_count_1}"

    # Assert Run 1: Verify survey item names
    survey_names_1 = db.execute(
        "SELECT name FROM kobo_asset_content__survey ORDER BY name"
    ).fetchall()
    assert len(survey_names_1) == 3
    assert survey_names_1[0][0] == "question_1"
    assert survey_names_1[1][0] == "question_2"
    assert survey_names_1[2][0] == "question_3"

    # Assert Run 1: Verify child records are linked to parent via _dlt_parent_id
    # DLT uses _dlt_parent_id to link child records to parent records
    parent_dlt_id_1 = db.execute("SELECT _dlt_id FROM kobo_asset_content").fetchone()[0]

    survey_parent_ids_1 = db.execute(
        "SELECT DISTINCT _dlt_parent_id FROM kobo_asset_content__survey"
    ).fetchall()
    assert len(survey_parent_ids_1) == 1
    assert survey_parent_ids_1[0][0] == parent_dlt_id_1

    # Arrange Run 2: Same asset but DIFFERENT content (2 new questions)
    content_run2 = make_asset_content_data(
        survey_items=[
            {
                "type": "text",
                "name": "question_4",
                "$kuid": "kuid_q4",
                "$xpath": "question_4",
                "$autoname": "question_4",
            },
            {
                "type": "decimal",
                "name": "question_5",
                "$kuid": "kuid_q5",
                "$xpath": "question_5",
                "$autoname": "question_5",
            },
        ],
        form_title="Test Form Run 2 - Updated",
    )

    # Mock endpoints for second run
    responses.add(
        responses.GET,
        asset_api_url,
        json=make_drf_response([asset]),
        status=200,
    )

    responses.add(
        responses.GET,
        content_api_url,
        json={"data": [content_run2]},
        status=200,
    )

    # Recreate resources for second run
    kobo_asset_2 = make_resource_kobo_asset(
        kobo_client=kobo_client,
        kobo_project_view_uid=project_view_uid,
        resource_name="kobo_asset",
        parallelized=False,
    )

    kobo_asset_content_2 = make_resource_kobo_asset_content(
        kobo_client=kobo_client,
        kobo_asset=kobo_asset_2,
        parallelized=False,
    )

    # Act: Run pipeline second time with updated content
    load_info_2 = kobo_pipeline.run(
        [kobo_asset_2, kobo_asset_content_2],
        write_disposition="merge",
    )

    # Assert Run 2: Pipeline completed successfully
    assert load_info_2.has_failed_jobs is False

    # ===== CRITICAL ASSERTIONS: Does merge work correctly with child tables? =====

    # Assert: Parent table STILL has exactly 1 record (no duplicate)
    parent_count_2 = db.execute("SELECT COUNT(*) FROM kobo_asset_content").fetchone()[0]
    assert parent_count_2 == 1, (
        f"Expected 1 parent record after merge, got {parent_count_2}. "
        "Merge should prevent duplicates!"
    )

    # Assert: Verify no duplicate asset_uids in parent table
    parent_duplicates = db.execute(
        """
        SELECT asset_uid, COUNT(*) as count
        FROM kobo_asset_content
        GROUP BY asset_uid
        HAVING count > 1
        """
    ).fetchall()
    assert len(parent_duplicates) == 0, (
        f"Found duplicate asset_uids: {parent_duplicates}"
    )

    # Assert: Child table has exactly 2 survey items (the NEW ones from run 2)
    child_count_2 = db.execute(
        "SELECT COUNT(*) FROM kobo_asset_content__survey"
    ).fetchone()[0]
    assert child_count_2 == 2, (
        f"Expected exactly 2 survey items after merge, got {child_count_2}. "
        f"Child table should reflect updated parent content (3 old → 2 new)."
    )

    # Assert: Child table has the NEW question names (q4, q5)
    survey_names_2 = db.execute(
        "SELECT name FROM kobo_asset_content__survey ORDER BY name"
    ).fetchall()
    assert len(survey_names_2) == 2
    assert survey_names_2[0][0] == "question_4", (
        "Expected question_4 from run 2, not found"
    )
    assert survey_names_2[1][0] == "question_5", (
        "Expected question_5 from run 2, not found"
    )

    # Assert: OLD questions (q1, q2, q3) are GONE (replaced, not appended)
    old_questions = db.execute(
        """
        SELECT name FROM kobo_asset_content__survey
        WHERE name IN ('question_1', 'question_2', 'question_3')
        """
    ).fetchall()
    assert len(old_questions) == 0, (
        f"Old questions should be removed after merge, but found: {old_questions}. "
        "This means child table is appending instead of merging!"
    )

    # Assert: All child records still linked to parent via _dlt_parent_id
    parent_dlt_id_2 = db.execute("SELECT _dlt_id FROM kobo_asset_content").fetchone()[0]

    survey_parent_ids_2 = db.execute(
        "SELECT DISTINCT _dlt_parent_id FROM kobo_asset_content__survey"
    ).fetchall()
    assert len(survey_parent_ids_2) == 1
    assert survey_parent_ids_2[0][0] == parent_dlt_id_2

    # Assert: Verify specific details of new questions (no data loss)
    question_4 = db.execute(
        "SELECT type, name, \"_kuid\" FROM kobo_asset_content__survey WHERE name = 'question_4'"
    ).fetchone()
    assert question_4 is not None, "question_4 should be present"
    assert question_4[0] == "text"
    assert question_4[1] == "question_4"
    assert question_4[2] == "kuid_q4"

    question_5 = db.execute(
        "SELECT type, name, \"_kuid\" FROM kobo_asset_content__survey WHERE name = 'question_5'"
    ).fetchone()
    assert question_5 is not None, "question_5 should be present"
    assert question_5[0] == "decimal"
    assert question_5[1] == "question_5"
    assert question_5[2] == "kuid_q5"
