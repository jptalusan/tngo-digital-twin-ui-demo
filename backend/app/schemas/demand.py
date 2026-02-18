from pydantic import BaseModel, Field


class DemandSummary(BaseModel):
    demand_name: str = Field(description="Scenario identifier derived from the CSV filename.")
    row_count: int = Field(description="Number of user rows loaded for this demand scenario.")


class DemandListResponse(BaseModel):
    demands: list[DemandSummary]
