"""Deterministic routing of explicit host decisions; never an intent classifier."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sbtd_project import TaskDataError
from sbtd_task_state import TaskSnapshot, TaskStore

_MODES = ("default", "lite", "strict")


@dataclass(frozen=True)
class ModeRecommendation:
    mode: str
    reason: str
    risk_id: str


@dataclass(frozen=True)
class RouteRequest:
    intent: str
    task_id: str | None = None
    explicit_mode: str | None = None
    read_only: bool = False
    confirmed: bool = False
    body: str = ""
    mode_note: str = "explicit user mode choice"
    recommendation: ModeRecommendation | None = None
    recommendation_response: str | None = None
    refusal_reason: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    status: str
    mode: str | None
    persisted: bool
    task: TaskSnapshot | None = None
    reason: str | None = None
    candidates: tuple[str, ...] = ()


class TaskRouter:
    def __init__(self, store: TaskStore) -> None:
        self.store = store
        self._session_notes: dict[str, str] = {}
        self._session_modes: dict[
            str, tuple[str, tuple[str | None, str, str] | None]
        ] = {}

    @staticmethod
    def _mode_stamp(task: TaskSnapshot) -> tuple[str | None, str, str]:
        fields = task.document.frontmatter
        return fields["workflow_mode"], fields["mode_source"], fields["mode_note"]

    @staticmethod
    def _note_parts(note: str) -> tuple[str, list[dict[str, str]]]:
        prefix = "SBTD mode decisions: "
        if not note.startswith(prefix):
            return note, []
        try:
            parsed = json.loads(note[len(prefix) :])
            if (
                not isinstance(parsed, dict)
                or set(parsed) != {"note", "refusals"}
                or not isinstance(parsed["note"], str)
                or not isinstance(parsed["refusals"], list)
                or any(
                    not isinstance(item, dict)
                    or set(item) != {"mode", "risk_id", "reason"}
                    or item["mode"] not in _MODES
                    or any(
                        not isinstance(value, str) or not value.strip()
                        for value in item.values()
                    )
                    for item in parsed["refusals"]
                )
            ):
                return note, []
            return parsed["note"], parsed["refusals"]
        except (ValueError, TypeError):
            return note, []

    def route(self, request: RouteRequest) -> RouteDecision:
        if request.intent not in ("new", "continue", "question"):
            raise ValueError("intent must be new, continue or question")
        if request.explicit_mode is not None and request.explicit_mode not in _MODES:
            raise ValueError("explicit mode must be default, lite or strict")
        recommendation = request.recommendation
        if recommendation is not None and (
            recommendation.mode not in _MODES
            or not recommendation.reason.strip()
            or not recommendation.risk_id.strip()
        ):
            raise ValueError(
                "recommendation requires a supported mode, reason and substantive risk identity"
            )
        if request.recommendation_response not in (None, "accept", "keep"):
            raise ValueError("recommendation response must be accept or keep")
        if request.recommendation_response is not None and recommendation is None:
            raise ValueError("a response requires its actual recommendation")
        read_only = (
            request.read_only or self.store.read_only or request.intent == "question"
        )
        mode = request.explicit_mode
        task: TaskSnapshot | None = None
        if request.intent == "continue":
            try:
                candidates = self.store.recovery_candidates(request.task_id)
            except TaskDataError as error:
                return RouteDecision("blocked", mode, False, reason=error.reason)
            if len(candidates) != 1:
                return RouteDecision(
                    "needs-task-choice",
                    None,
                    False,
                    reason="select the task before deciding its execution mode",
                    candidates=tuple(
                        item.document.frontmatter["id"] for item in candidates
                    ),
                )
            task = candidates[0]
            key = task.document.frontmatter["id"]
            pending = self._session_modes.get(key)
            if pending is not None and pending[1] != self._mode_stamp(task):
                self._session_modes.pop(key, None)
                self._session_notes.pop(key, None)
                pending = None
            mode = mode or (
                pending[0]
                if pending is not None
                else task.document.frontmatter["workflow_mode"]
            )
            if mode is None:
                return RouteDecision(
                    "needs-mode-choice",
                    None,
                    False,
                    task,
                    "choose the selected task's unresolved mode",
                )
        else:
            pending = (
                self._session_modes.get(request.task_id)
                if request.intent == "new" and request.task_id is not None
                else None
            )
            mode = mode or (pending[0] if pending is not None else "default")
        if request.intent == "new" and request.task_id is None and not read_only:
            return RouteDecision(
                "needs-task-choice",
                mode,
                False,
                reason="choose a logical ID before creating persistent state",
            )
        key = request.task_id or (
            task.document.frontmatter["id"] if task is not None else None
        )
        note = self._session_notes.get(
            key or "",
            task.document.frontmatter["mode_note"]
            if task is not None
            else request.mode_note,
        )
        prior_note, refusals = self._note_parts(note)
        save_choice = request.explicit_mode is not None
        accepted_note: str | None = None
        needs_recommendation = False
        if recommendation is not None and recommendation.mode != mode:
            refused = any(
                item["mode"] == recommendation.mode
                and item["risk_id"] == recommendation.risk_id
                for item in refusals
            )
            if request.recommendation_response is None and not refused:
                needs_recommendation = True
            if request.recommendation_response == "accept":
                mode = recommendation.mode
                refusals = [
                    item for item in refusals
                    if (item["mode"], item["risk_id"])
                    != (recommendation.mode, recommendation.risk_id)
                ]
                accepted_note = (
                    f"accepted recommendation {recommendation.mode} "
                    f"({recommendation.risk_id}): {recommendation.reason}"
                )
                save_choice = True
            elif request.recommendation_response == "keep":
                if request.refusal_reason is None or not request.refusal_reason.strip():
                    raise ValueError(
                        "keeping the current mode requires the user's refusal reason"
                    )
                if not refused:
                    refusals = [
                        *refusals,
                        {
                            "mode": recommendation.mode,
                            "risk_id": recommendation.risk_id,
                            "reason": request.refusal_reason,
                        },
                    ]
                save_choice = True
        if save_choice:
            note = accepted_note or (
                request.mode_note if request.explicit_mode is not None else prior_note
            )
            if refusals:
                note = "SBTD mode decisions: " + json.dumps(
                    {"note": note, "refusals": refusals},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            if (
                task is not None
                and self._mode_stamp(task) == (mode, "user", note)
            ):
                save_choice = False
            if save_choice and key is not None:
                self._session_notes[key] = note
                self._session_modes[key] = (
                    mode,
                    self._mode_stamp(task) if task is not None else None,
                )
        if task is not None and not read_only:
            try:
                binding = self.store.current_binding()
            except TaskDataError as error:
                return RouteDecision("blocked", mode, False, task, error.reason)
            if binding != task.document.frontmatter["branch"]:
                return RouteDecision(
                    "needs-branch-choice",
                    mode,
                    False,
                    task,
                    "choose the correct worktree, explicitly rebind, or continue read-only",
                )
        if needs_recommendation:
            assert recommendation is not None
            return RouteDecision(
                "needs-mode-decision",
                mode,
                False,
                task,
                f"recommend {recommendation.mode}: {recommendation.reason}; keep {mode} or accept explicitly",
            )
        if read_only:
            return RouteDecision(
                "ready",
                mode,
                False,
                task,
                "choice remains in conversation; no state was written",
            )
        pending_choice = key is not None and key in self._session_modes
        if task is not None and not save_choice and not pending_choice:
            return RouteDecision("ready", mode, True, task)
        if not request.confirmed:
            return RouteDecision(
                "needs-persistence-confirmation",
                mode,
                False,
                task,
                "mode is effective for this session but has not been saved",
            )
        try:
            if task is not None:
                saved = self.store.set_mode(
                    task.document.frontmatter["id"], mode, note=note, confirmed=True
                )
            else:
                assert request.task_id is not None
                saved = self.store.create(
                    request.task_id,
                    body=request.body,
                    mode=mode if save_choice or pending_choice else None,
                    mode_note=note if save_choice or pending_choice else None,
                    confirmed=True,
                )
        except TaskDataError as error:
            return RouteDecision("persistence-failed", mode, False, task, error.reason)
        if key is not None:
            self._session_modes.pop(key, None)
            self._session_notes.pop(key, None)
        return RouteDecision("ready", mode, True, saved)
