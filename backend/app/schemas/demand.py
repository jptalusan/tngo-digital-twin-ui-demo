from pydantic import BaseModel, Field


class DemandSummary(BaseModel):
    demand_name: str = Field(description="Scenario identifier derived from the CSV filename.")
    row_count: int = Field(description="Number of user rows loaded for this demand scenario.")


class DemandListResponse(BaseModel):
    demands: list[DemandSummary]


class DemandPreviewPoint(BaseModel):
    home_lat: float
    home_lon: float
    work_lat: float
    work_lon: float
    shift: int
    shift_start: str  # "HH:MM:SS"
    shift_end: str    # "HH:MM:SS"


class DemandPreviewResponse(BaseModel):
    demand_name: str
    total_count: int
    sampled_count: int
    points: list[DemandPreviewPoint]
