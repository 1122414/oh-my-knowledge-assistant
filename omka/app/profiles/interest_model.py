from pydantic import BaseModel


class InterestProfile(BaseModel):
    name: str
    keywords: list[str]
    weight: float = 1.0


class ProjectProfile(BaseModel):
    name: str
    keywords: list[str]
    weight: float = 1.0


class UserProfile(BaseModel):
    interests: list[InterestProfile]
    projects: list[ProjectProfile]

    @classmethod
    def load(cls) -> "UserProfile":
        from omka.app.profiles.profile_loader import load_interests, load_projects

        interests = [InterestProfile(**i) for i in load_interests()]
        projects = [ProjectProfile(**p) for p in load_projects()]
        return cls(interests=interests, projects=projects)
