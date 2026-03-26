from app.domain.analyse_job import _build_executable_code, _execution_succeeded, _is_placeholder_message


def test_execution_succeeded_true_when_ok_zero_and_no_stderr() -> None:
    result = {"ok": True, "returncode": 0, "stderr": ""}
    assert _execution_succeeded(result) is True


def test_execution_succeeded_false_with_nonzero_returncode() -> None:
    result = {"ok": True, "returncode": 1, "stderr": ""}
    assert _execution_succeeded(result) is False


def test_execution_succeeded_false_with_stderr() -> None:
    result = {"ok": True, "returncode": 0, "stderr": "boom"}
    assert _execution_succeeded(result) is False


def test_build_executable_code_bootstraps_df_when_missing() -> None:
    generated = _build_executable_code("print(df.head())", "/data/raw_uploads/sample.csv")
    assert "pd.read_csv('/data/raw_uploads/sample.csv')" in generated
    assert "print(df.head())" in generated


def test_build_executable_code_keeps_existing_loader() -> None:
    code = "import pandas as pd\ndf = pd.read_csv('/data/raw_uploads/sample.csv')\nprint(df.head())"
    generated = _build_executable_code(code, "/data/raw_uploads/sample.csv")
    assert generated == code


def test_placeholder_message_detection() -> None:
    assert _is_placeholder_message("The user has requested for the top 5 rows") is True
    assert _is_placeholder_message("Top 5 rows are shown below") is False
