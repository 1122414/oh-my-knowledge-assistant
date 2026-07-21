"""Evidence-driven user profile assembled from explicit configuration and memory."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import select

from omka.app.profiles.profile_loader import load_interests, load_projects
from omka.app.services.memory_service import MemoryService
from omka.app.storage.db import MemoryEvent, MemoryItem, get_session

ProfileCategory = Literal[
    "interest",
    "project",
    "preference",
    "working_style",
    "avoidance",
    "goal",
]


class ProfileEvidence(BaseModel):
    id: str
    source_type: str
    source_ref: str | None = None
    confidence: float = Field(ge=0, le=1)
    status: str
    user_confirmed: bool = False
    updated_at: datetime | None = None


class ProfileFacet(BaseModel):
    key: str
    category: ProfileCategory
    label: str
    value: str
    confidence: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    state: Literal["verified", "inferred", "review"]
    memory_id: str | None = None
    evidence: list[ProfileEvidence] = Field(default_factory=list)


class UserProfileSnapshot(BaseModel):
    owner_external_id: str
    summary: str
    facets: list[ProfileFacet]
    confidence: float = Field(ge=0, le=1)
    coverage_score: float = Field(ge=0, le=1)
    confirmation_rate: float = Field(ge=0, le=1)
    candidate_count: int
    conflict_count: int
    updated_at: datetime

    def to_context(self) -> dict[str, str]:
        grouped: dict[str, list[str]] = {
            "interest": [],
            "project": [],
            "preference": [],
            "working_style": [],
            "avoidance": [],
            "goal": [],
        }
        for facet in self.facets:
            grouped[facet.category].append(
                f"{facet.value}（置信度 {facet.confidence:.0%}，{facet.state}）"
            )
        return {
            "interests": "；".join(grouped["interest"]),
            "projects": "；".join(grouped["project"]),
            "preferences": "；".join(
                grouped["preference"] + grouped["working_style"]
            ),
            "avoidances": "；".join(grouped["avoidance"]),
            "goals": "；".join(grouped["goal"]),
            "profile_summary": self.summary,
            "profile_confidence": f"{self.confidence:.2f}",
        }


class UserProfileService:
    """Builds a compact profile with inspectable evidence and confidence."""

    _NEGATIVE = ("不喜欢", "避免", "不要", "不想", "拒绝")

    @classmethod
    def build_snapshot(cls, owner_external_id: str = "local") -> UserProfileSnapshot:
        facets: dict[str, ProfileFacet] = {}
        cls._add_config_facets(facets)

        memories = MemoryService.list_memories(
            owner_external_id=owner_external_id,
            limit=500,
        )
        confirmed_ids = cls._confirmed_memory_ids([memory.id for memory in memories])
        for memory in memories:
            if memory.status not in {"active", "candidate"}:
                continue
            category = cls._category(memory)
            if category is None:
                continue
            label = cls._memory_label(memory)
            key = cls._facet_key(category, label)
            user_confirmed = memory.id in confirmed_ids or memory.source_type == "manual"
            state: Literal["verified", "inferred", "review"]
            if memory.status == "candidate":
                state = "review"
            elif user_confirmed:
                state = "verified"
            else:
                state = "inferred"
            confidence = cls._calibrated_confidence(memory, user_confirmed)
            evidence = ProfileEvidence(
                id=memory.id,
                source_type=memory.source_type,
                source_ref=memory.source_ref,
                confidence=confidence,
                status=memory.status,
                user_confirmed=user_confirmed,
                updated_at=memory.updated_at,
            )
            existing = facets.get(key)
            if existing:
                existing.evidence.append(evidence)
                if confidence >= existing.confidence:
                    existing.value = memory.content
                    existing.confidence = confidence
                    existing.importance = memory.importance
                    existing.state = state
                    existing.memory_id = memory.id
                continue
            facets[key] = ProfileFacet(
                key=key,
                category=category,
                label=label,
                value=memory.content,
                confidence=confidence,
                importance=memory.importance,
                state=state,
                memory_id=memory.id,
                evidence=[evidence],
            )

        ordered = sorted(
            facets.values(),
            key=lambda facet: (
                facet.state == "verified",
                facet.importance,
                facet.confidence,
            ),
            reverse=True,
        )
        candidate_count = sum(1 for facet in ordered if facet.state == "review")
        verified_count = sum(1 for facet in ordered if facet.state == "verified")
        conflict_count = cls._count_conflicts(ordered)
        confidence = (
            sum(facet.confidence for facet in ordered) / len(ordered)
            if ordered
            else 0.0
        )
        confirmation_rate = verified_count / len(ordered) if ordered else 0.0
        covered_categories = len({facet.category for facet in ordered})
        coverage_score = min(1.0, covered_categories / 4)
        summary = cls._summary(ordered)
        return UserProfileSnapshot(
            owner_external_id=owner_external_id,
            summary=summary,
            facets=ordered,
            confidence=round(confidence, 3),
            coverage_score=round(coverage_score, 3),
            confirmation_rate=round(confirmation_rate, 3),
            candidate_count=candidate_count,
            conflict_count=conflict_count,
            updated_at=datetime.utcnow(),
        )

    @classmethod
    def _add_config_facets(cls, facets: dict[str, ProfileFacet]) -> None:
        for category, rows in (
            ("interest", load_interests()),
            ("project", load_projects()),
        ):
            for row in rows:
                name = str(row.get("name") or "").strip()
                if not name:
                    continue
                keywords = [
                    str(keyword)
                    for keyword in row.get("keywords", [])
                    if str(keyword).strip()
                ]
                value = name
                if keywords:
                    value += f"；关键词：{', '.join(keywords)}"
                key = cls._facet_key(category, name)
                evidence_id = f"profile:{category}:{cls._stable_id(name)}"
                weight = min(1.0, max(0.0, float(row.get("weight", 1.0))))
                facets[key] = ProfileFacet(
                    key=key,
                    category=category,
                    label=name,
                    value=value,
                    confidence=0.95,
                    importance=weight,
                    state="verified",
                    evidence=[
                        ProfileEvidence(
                            id=evidence_id,
                            source_type="profile_config",
                            source_ref=f"data/profiles/{category}s.yaml",
                            confidence=0.95,
                            status="active",
                            user_confirmed=True,
                        )
                    ],
                )

    @staticmethod
    def _confirmed_memory_ids(memory_ids: list[str]) -> set[str]:
        if not memory_ids:
            return set()
        with get_session() as session:
            events = session.exec(
                select(MemoryEvent).where(
                    MemoryEvent.memory_id.in_(memory_ids),
                    MemoryEvent.event_type == "confirmed",
                )
            ).all()
        return {event.memory_id for event in events}

    @classmethod
    def _category(cls, memory: MemoryItem) -> ProfileCategory | None:
        subject = memory.subject.lower()
        content = memory.content.lower()
        if any(signal in content for signal in cls._NEGATIVE):
            return "avoidance"
        if subject in {"interest", "user_profile"}:
            return "interest"
        if subject == "project":
            return "project"
        if subject in {"preference", "setting"}:
            return "preference"
        if subject in {"working_style", "style"}:
            return "working_style"
        if subject in {"task", "goal"}:
            return "goal"
        return None

    @staticmethod
    def _memory_label(memory: MemoryItem) -> str:
        profile_name = memory.metadata_json.get("profile_name")
        if isinstance(profile_name, str) and profile_name.strip():
            return profile_name.strip()
        candidate_title = memory.metadata_json.get("candidate_title")
        if isinstance(candidate_title, str) and candidate_title.strip():
            return candidate_title.strip()
        if memory.source_type == "feedback" and memory.source_ref:
            reference_label = memory.source_ref.rsplit(":", 1)[-1].strip()
            if reference_label:
                return reference_label
        meaningful_tags = [
            tag
            for tag in memory.tags
            if tag not in {"interest", "project", "preference", "feedback"}
        ]
        if meaningful_tags:
            return meaningful_tags[0]
        compact = re.sub(r"\s+", " ", memory.content).strip()
        return compact[:32]

    @staticmethod
    def _calibrated_confidence(
        memory: MemoryItem,
        user_confirmed: bool,
    ) -> float:
        confidence = memory.confidence
        if memory.status == "candidate":
            confidence *= 0.72
        if user_confirmed:
            confidence = max(confidence, 0.92)
        if memory.source_type == "feedback":
            confidence = max(confidence, 0.86)
        return round(min(1.0, max(0.0, confidence)), 3)

    @classmethod
    def _count_conflicts(cls, facets: list[ProfileFacet]) -> int:
        by_label: dict[str, set[bool]] = {}
        for facet in facets:
            label = cls._normalize(facet.label)
            if not label:
                continue
            by_label.setdefault(label, set()).add(
                any(signal in facet.value for signal in cls._NEGATIVE)
            )
        return sum(1 for polarities in by_label.values() if len(polarities) > 1)

    @staticmethod
    def _summary(facets: list[ProfileFacet]) -> str:
        if not facets:
            return "画像尚为空；Agent 会优先依赖当前问题，不会猜测长期偏好。"
        category_labels = {
            "interest": "兴趣",
            "project": "项目",
            "preference": "偏好",
            "working_style": "工作方式",
            "avoidance": "避免事项",
            "goal": "长期目标",
        }
        parts: list[str] = []
        for category in category_labels:
            values = [
                facet.label
                for facet in facets
                if facet.category == category and facet.state != "review"
            ][:3]
            if values:
                parts.append(f"{category_labels[category]}：{'、'.join(values)}")
        return "；".join(parts) or "当前画像仅含待确认信息，使用前需要用户校准。"

    @classmethod
    def _facet_key(cls, category: str, label: str) -> str:
        return f"{category}:{cls._stable_id(cls._normalize(label))}"

    @staticmethod
    def _stable_id(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[\W_]+", "", value.lower(), flags=re.UNICODE)
