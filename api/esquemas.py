from pydantic import BaseModel, ConfigDict, Field
from servicio_modelo import ejemplo

class Causa(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [ejemplo],
        },
    )

    localidad_nombre: str = Field(
        min_length=1,
        max_length=150,
    )

    juzgado_numero: str = Field(
        min_length=1,
        max_length=100,
    )

    causa_objeto_litigio_descripcion: str = Field(
        min_length=1,
        max_length=500,
    )


