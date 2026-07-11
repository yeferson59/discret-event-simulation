"""Distribuciones de probabilidad para tiempos de llegada y servicio.

Cada distribución implementa `.sample()` -> float >= 0. El motor de simulación
solo conoce esta interfaz, nunca los parámetros internos de cada tipo. Esto
permite agregar una nueva distribución (ej. lognormal) sin tocar el motor,
los parsers de entrada, ni las capas de salida.

Todas muestrean con el módulo `random` de la stdlib (no numpy): así una sola
llamada a `random.seed(n)` — la que hace `core.engine.Engine` cuando recibe
`seed` — vuelve reproducible la corrida completa, tiempos y enrutamiento.
"""

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class Distribution(ABC):
    """Interfaz común para todas las distribuciones usadas en el simulador."""

    @abstractmethod
    def sample(self) -> float:
        """Devuelve una muestra >= 0 (un tiempo de servicio o entre-llegada)."""
        raise NotImplementedError

    @classmethod
    def from_spec(cls, kind: str, params: dict) -> "Distribution":
        """Fábrica: construye la distribución correcta a partir del tipo leído
        del archivo de entrada (.DEF extendido o XML).

        Ejemplo:
            Distribution.from_spec("triangular", {"low": 1, "mode": 2, "high": 5})
        """
        registry = {
            "exp": Exponential,
            "exponential": Exponential,
            "uniforme": Uniform,
            "uniform": Uniform,
            "triangular": Triangular,
            "normal": Normal,
            "tabla": Empirical,
            "table": Empirical,
            "triangularinverse": TriangularInverse,
            "lognormal": LogNormal,
            "beta": Beta,
            "gamma": Gamma,
            "weibull": Weibull,
            "pareto": Pareto,
            "parento": Pareto,  # alias por typo histórico, para archivos viejos
        }

        kind_key = kind.strip().lower()

        if kind_key not in registry:
            raise ValueError(
                f"Distribución desconocida: '{kind}'. Opciones válidas: "
                f"{sorted(set(registry.keys()))}"
            )

        return registry[kind_key](**params)


@dataclass
class Exponential(Distribution):
    mean: float

    def sample(self) -> float:
        if self.mean <= 0:
            return 0.0

        return random.expovariate(1.0 / self.mean)


@dataclass
class Uniform(Distribution):
    a: float
    b: float

    def __post_init__(self) -> None:
        if self.a > self.b:
            raise ValueError(f"Uniforme: a ({self.a}) debe ser <= b ({self.b})")

    def sample(self) -> float:
        return random.uniform(self.a, self.b)


@dataclass
class Triangular(Distribution):
    low: float
    mode: float
    high: float

    def __post_init__(self) -> None:
        if not (self.low <= self.mode <= self.high):
            raise ValueError(
                f"Triangular: se requiere low <= mode <= high "
                f"({self.low} <= {self.mode} <= {self.high})"
            )

    def sample(self) -> float:
        return random.triangular(self.low, self.high, self.mode)


@dataclass
class TriangularInverse(Distribution):
    low: float
    mode: float
    high: float

    def __post_init__(self) -> None:
        if not (self.low <= self.mode <= self.high):
            raise ValueError(
                f"Triangular: se requiere low <= mode <= high "
                f"({self.low} <= {self.mode} <= {self.high})"
            )

    def sample(self) -> float:
        fc = (self.mode - self.low) / (self.high - self.low)
        u = random.random()

        if u < fc:
            return self.low + math.sqrt(
                u * (self.high - self.low) * (self.mode - self.low)
            )
        else:
            return self.high - math.sqrt(
                (1 - u) * (self.high - self.low) * (self.high - self.mode)
            )


@dataclass
class Normal(Distribution):
    mu: float
    sigma: float
    floor_at_zero: bool = True

    def sample(self) -> float:
        value = random.gauss(self.mu, self.sigma)

        if self.floor_at_zero:
            return max(0.0, value)

        return value


@dataclass
class LogNormal(Distribution):
    mean: float
    sigma: float
    floor_at_zero: bool = True

    def sample(self) -> float:
        value = random.lognormvariate(self.mean, self.sigma)

        if self.floor_at_zero:
            return max(0.0, value)

        return value


@dataclass
class Beta(Distribution):
    a: float
    b: float

    def __post_init__(self) -> None:
        if not (self.a > 0 and self.b > 0):
            raise ValueError(f"{self.a} > 0 y {self.b} > 0")

    def sample(self) -> float:
        return random.betavariate(self.a, self.b)


@dataclass
class Gamma(Distribution):
    alpha: float
    beta: float

    def __post_init__(self) -> None:
        if not (self.alpha > 0 and self.beta > 0):
            raise ValueError(f"{self.alpha} > 0 y {self.beta} > 0")

    def sample(self) -> float:
        return random.gammavariate(self.alpha, self.beta)


@dataclass
class Weibull(Distribution):
    a: float

    def __post_init__(self) -> None:
        if self.a <= 0:
            raise ValueError(f"Weibull: a ({self.a}) debe ser > 0")

    def sample(self) -> float:
        # weibullvariate(escala, forma); escala 1 igual que np.random.weibull(a).
        return random.weibullvariate(1.0, self.a)


@dataclass
class Pareto(Distribution):
    a: float

    def __post_init__(self) -> None:
        if self.a <= 0:
            raise ValueError(f"Pareto: a ({self.a}) debe ser > 0")

    def sample(self) -> float:
        # paretovariate devuelve muestras >= 1; se desplaza a [0, inf) para
        # que sirva como tiempo (mismo comportamiento que np.random.pareto).
        return random.paretovariate(self.a) - 1.0


@dataclass
class Empirical(Distribution):
    """Distribución tipo tabla: valores discretos con probabilidades acumuladas.

    Mismo patrón que el enrutamiento (succ/prob): la última probabilidad
    acumulada debe ser 1.0.

    Formato esperado:
        Empirical(values=[1.0, 2.0, 3.0], cum_probs=[0.3, 0.7, 1.0])
    """

    values: list[float] = field(default_factory=list)
    cum_probs: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.values) != len(self.cum_probs):
            raise ValueError(
                "Empirical: values y cum_probs deben tener el mismo tamaño"
            )

        if self.cum_probs and abs(self.cum_probs[-1] - 1.0) > 1e-6:
            raise ValueError("Empirical: la última probabilidad acumulada debe ser 1.0")

    def sample(self) -> float:
        r = random.random()

        for value, cum_p in zip(self.values, self.cum_probs):
            if r <= cum_p:
                return value

        return self.values[-1]
