from __future__ import annotations

from pathlib import Path

import typer

from apps.contract_intelligence.evaluation.corpus import default_corpus_dir, evaluate_corpus
from apps.contract_intelligence.orchestration.ese_bridge import run_bid_review_with_ese
from apps.contract_intelligence.orchestration.bid_review_runner import run_bid_review


app = typer.Typer(help="Contract intelligence pilot CLI")


@app.callback()
def main() -> None:
    """Run contract-intelligence pilot workflows."""


@app.command("bid-review")
def bid_review(
    project_dir: str = typer.Argument(..., help="Path to the project document folder"),
    artifacts_dir: str | None = typer.Option(
        None,
        "--artifacts-dir",
        help="Optional output directory for generated bid-review artifacts",
    ),
) -> None:
    """Run the deterministic construction bid-review pilot over a project folder."""
    result = run_bid_review(project_dir=project_dir, artifacts_dir=artifacts_dir)
    typer.echo(f"Project: {result.project_id}")
    typer.echo(f"Artifacts: {result.artifacts_dir}")
    typer.echo(f"Recommendation: {result.decision_summary.recommendation.value}")
    typer.echo(f"Overall risk: {result.decision_summary.overall_risk.value}")
    typer.echo(f"Human review required: {result.decision_summary.human_review_required}")
    typer.echo("Artifacts written:")
    for filename in sorted(result.artifact_paths):
        relative = Path(result.artifact_paths[filename]).resolve()
        typer.echo(f"  - {filename}: {relative}")


@app.command("evaluate-corpus")
def evaluate_corpus_command(
    corpus_dir: str = typer.Option(
        str(default_corpus_dir()),
        "--corpus-dir",
        help="Directory containing gold-corpus cases with expected.json and inputs/.",
    ),
    artifacts_dir: str | None = typer.Option(
        None,
        "--artifacts-dir",
        help="Optional root directory where evaluation artifacts will be written.",
    ),
) -> None:
    """Run the deterministic gold-corpus evaluation suite for the pilot."""
    results = evaluate_corpus(corpus_dir=corpus_dir, artifacts_root=artifacts_dir)
    passed = 0
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {result.case_id} -> {result.artifacts_dir}")
        for failure in result.failures:
            typer.echo(f"  - {failure}")
        if result.passed:
            passed += 1
    typer.echo(f"Summary: {passed}/{len(results)} cases passed")
    if passed != len(results):
        raise typer.Exit(code=1)


@app.command("ensemble-bid-review")
def ensemble_bid_review(
    project_dir: str = typer.Argument(..., help="Path to the project document folder"),
    provider: str = typer.Option("local", help="Provider preset for the ESE-backed run"),
    execution_mode: str = typer.Option("demo", help="auto, demo, or live"),
    artifacts_dir: str = typer.Option(
        "artifacts/contract_intelligence_ese",
        help="Directory for ESE-backed run artifacts",
    ),
    model: str | None = typer.Option(None, help="Optional provider model override"),
    runtime_adapter: str | None = typer.Option(None, help="Optional module:function adapter for advanced live runs"),
    provider_name: str | None = typer.Option(None, help="Custom provider name when using custom_api"),
    base_url: str | None = typer.Option(None, help="Base URL for custom_api or local live runs"),
    api_key_env: str | None = typer.Option(None, help="API key environment variable override"),
    fail_on_high: bool = typer.Option(False, help="Fail closed on HIGH/CRITICAL findings during the ESE run"),
    write_config_path: str | None = typer.Option(None, "--write-config", help="Optional path to save the generated ESE config"),
) -> None:
    """Run the construction bid review through ESE's real orchestration path."""
    cfg, summary_path = run_bid_review_with_ese(
        project_dir=project_dir,
        provider=provider,
        execution_mode=execution_mode,
        artifacts_dir=artifacts_dir,
        model=model,
        api_key_env=api_key_env,
        runtime_adapter=runtime_adapter,
        provider_name=provider_name,
        base_url=base_url,
        fail_on_high=fail_on_high,
        config_path=write_config_path,
    )
    adapter_name = str((cfg.get("runtime") or {}).get("adapter") or "dry-run")
    typer.echo(f"ESE-backed bid review completed via {adapter_name}. Summary: {summary_path}")


if __name__ == "__main__":
    app()
