import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Password = Annotated[str, StringConstraints(strip_whitespace=False)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Register(Input):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: Password = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value: str) -> str:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Email invalido")
        return value.lower()


class Login(Input):
    email: str = Field(max_length=254)
    password: Password = Field(min_length=1, max_length=128)


class PasswordChange(Input):
    current_password: Password = Field(min_length=1, max_length=128)
    new_password: Password = Field(min_length=10, max_length=128)


class RoleUpdate(Input):
    role: Literal["admin", "editor", "viewer"]
    active: bool = True


class SourceInput(Input):
    name: str = Field(min_length=2, max_length=100)
    kind: Literal["csv", "excel", "json", "api"]
    url: str | None = Field(default=None, max_length=2000)
    credential_env: str | None = Field(default=None, pattern=r"^DATAPULSE_API_[A-Z0-9_]+$", max_length=100)

    @model_validator(mode="after")
    def api_url(self):
        if self.kind == "api":
            parts = urlsplit(self.url or "")
            if (parts.scheme != "https" or not parts.hostname or parts.username
                    or parts.password or parts.port not in (None, 443) or parts.fragment
                    or parts.query):
                raise ValueError("API requer URL HTTPS sem credenciais, query ou fragmento")
        elif self.url or self.credential_env:
            raise ValueError("URL e credencial sao permitidas apenas para APIs")
        return self


class Column(Input):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["string", "number", "date", "boolean"]
    required: bool = False


class DatasetMetadata(Input):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=2000)
    source_id: int | None = Field(default=None, gt=0)


class DatasetInput(DatasetMetadata):
    columns: list[Column] = Field(default_factory=list, max_length=100)

    @field_validator("columns")
    @classmethod
    def unique_columns(cls, value: list[Column]) -> list[Column]:
        if len({c.name for c in value}) != len(value):
            raise ValueError("Nomes de colunas devem ser unicos")
        return value


class Filter(Input):
    field: str = Field(min_length=1, max_length=100)
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains"]
    value: str | float | bool | None


class AnalyticsQuery(Input):
    dataset_id: int = Field(gt=0)
    aggregation: Literal["count", "sum", "avg", "min", "max"] = "count"
    field: str | None = Field(default=None, max_length=100)
    group_by: list[str] = Field(default_factory=list, max_length=2)
    date_field: str | None = Field(default=None, max_length=100)
    period: Literal["day", "week", "month", "year"] = "month"
    filters: list[Filter] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def required_field(self):
        if self.aggregation != "count" and not self.field:
            raise ValueError("Agregacao numerica requer field")
        if len(set(self.group_by)) != len(self.group_by):
            raise ValueError("Agrupamentos duplicados")
        return self


class KPIInput(Input):
    name: str = Field(min_length=2, max_length=100)
    query: AnalyticsQuery
    target: float | None = None


class AlertInput(Input):
    name: str = Field(min_length=2, max_length=100)
    kpi_id: int = Field(gt=0)
    operator: Literal["gt", "gte", "lt", "lte", "eq"]
    threshold: float
    enabled: bool = True


class ReportInput(Input):
    name: str = Field(min_length=2, max_length=100)
    query: AnalyticsQuery


class FavoriteInput(ReportInput):
    pass


class ScheduleInput(Input):
    name: str = Field(min_length=2, max_length=100)
    kind: Literal["import", "report"]
    dataset_id: int = Field(gt=0)
    query: AnalyticsQuery | None = None
    interval_minutes: int = Field(ge=15, le=43200)
    enabled: bool = True
    email_report: bool = False

    @model_validator(mode="after")
    def report_query(self):
        if self.kind == "report":
            if self.query is None or self.query.dataset_id != self.dataset_id:
                raise ValueError("Relatorio requer consulta do mesmo dataset")
        elif self.query is not None or self.email_report:
            raise ValueError("Importacao nao aceita consulta nem email de relatorio")
        return self


class ScheduleState(Input):
    enabled: bool
