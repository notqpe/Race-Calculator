from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class RaceParams:
    duration_hours: float       # длительность гонки, ч
    avg_lap_sec: float          # среднее время круга, сек
    tank_liters: float          # объём бака, л
    pit_refuel_sec: float       # время пит-стопа только с дозаправкой, сек
    pit_tyre_sec: float         # время пит-стопа с заменой резины, сек
    driver_change_sec: float    # время смены пилота, сек


@dataclass
class TyreParams:
    sets: int                   # количество комплектов шин


@dataclass
class Pilot:
    name: str
    lap_time_sec: float         # среднее время круга, сек
    # режим 1: расход на круг
    fuel_push: float            # л/круг
    fuel_eco: float             # л/круг
    # режим 2: кругов на баке
    laps_per_tank_push: float   # кругов на баке (push)
    laps_per_tank_eco: float    # кругов на баке (eco)


@dataclass
class Stint:
    pilot: str
    laps: int
    fuel_start: float
    tyre_set: int               # номер комплекта шин (1..N)
    eco: bool                   # True, если стинт должен ехаться в экономии


@dataclass
class ConsumptionMode:
    """Режим ввода расхода."""
    by_fuel_per_lap: bool       # True: fuel_push/fuel_eco, False: laps_per_tank_*


def _build_pilots(
    pilot_tuples: List[Tuple[str, float, float, float, float, float]]
) -> List[Pilot]:
    """
    pilot_tuples:
      (name, lap_time_sec, fuel_push, fuel_eco, laps_per_tank_push, laps_per_tank_eco)
    """
    pilots: List[Pilot] = []
    for name, lap_time_sec, fuel_push, fuel_eco, l_push, l_eco in pilot_tuples:
        pilots.append(Pilot(
            name=name,
            lap_time_sec=lap_time_sec,
            fuel_push=fuel_push,
            fuel_eco=fuel_eco,
            laps_per_tank_push=l_push,
            laps_per_tank_eco=l_eco,
        ))
    return pilots


def _calc_total_laps(race: RaceParams) -> int:
    race_sec = race.duration_hours * 3600.0
    if race.avg_lap_sec <= 0:
        return 0
    laps = int(race_sec // race.avg_lap_sec)
    return max(laps, 0)


def _calc_stint_length_push(race: RaceParams, pilot: Pilot, mode: ConsumptionMode) -> int:
    """Длина одного стинта по баку в кругах (push)."""
    if mode.by_fuel_per_lap:
        if pilot.fuel_push <= 0:
            return 0
        laps = int(race.tank_liters // pilot.fuel_push)
    else:
        if pilot.laps_per_tank_push <= 0:
            return 0
        laps = int(pilot.laps_per_tank_push)
    return max(laps, 1)


def _assign_tyres(num_stints: int, tyre: TyreParams) -> List[int]:
    """
    2 стинта на комплект, при нехватке – часть комплектов по 3 стинта.
    Возвращает индексы комплектов 0..sets-1.
    """
    sets = max(tyre.sets, 1)
    base_capacity = 2 * sets

    if num_stints <= base_capacity:
        result: List[int] = []
        tyre_index = 0
        used_on_current = 0
        for _ in range(num_stints):
            result.append(tyre_index)
            used_on_current += 1
            if used_on_current == 2:
                tyre_index = min(tyre_index + 1, sets - 1)
                used_on_current = 0
        return result

    extra = num_stints - base_capacity
    sets_with_3 = min(extra, sets)

    counts = [2] * sets
    for i in range(sets_with_3):
        counts[i] += 1

    result: List[int] = []
    for tyre_index, c in enumerate(counts):
        for _ in range(c):
            result.append(tyre_index)

    while len(result) < num_stints:
        result.append(sets - 1)

    return result[:num_stints]


def plan_stints(
    race: RaceParams,
    tyre: TyreParams,
    pilot_tuples: List[Tuple[str, float, float, float, float, float]],
    mode: ConsumptionMode,
) -> List[Stint]:
    """
    Планирование:
      1) считаем общее число кругов;
      2) считаем длину стинта по баку (push) для первого пилота;
      3) определяем сколько стинтов надо;
      4) распределяем стинты по комплектам шин (2/3 стинта на комплект);
      5) каждому комплекту даём одного пилота (по порядку в списке);
      6) если последний стинт слишком короткий — пытаемся раздать его
         круги в два предыдущих и пометить их как eco.
    """
    pilots = _build_pilots(pilot_tuples)
    if not pilots:
        return []

    total_laps = _calc_total_laps(race)
    if total_laps <= 0:
        return []

    base_stint_len = _calc_stint_length_push(race, pilots[0], mode)
    if base_stint_len <= 0:
        return []

    # сколько стинтов нужно всего
    num_stints = (total_laps + base_stint_len - 1) // base_stint_len

    # распределяем стинты по комплектам (индексы 0..sets-1)
    tyre_indices = _assign_tyres(num_stints, tyre)

    # привязка пилота к комплекту шин:
    # комплект 0 -> пилот 0, комплект 1 -> пилот 1, ..., по кругу
    set_to_pilot = {}
    for idx in set(tyre_indices):
        set_to_pilot[idx] = pilots[idx % len(pilots)]

    stints: List[Stint] = []
    laps_left = total_laps

    for i in range(num_stints):
        tyre_index = tyre_indices[i]
        pilot = set_to_pilot[tyre_index]

        stint_len = base_stint_len
        if stint_len > laps_left:
            stint_len = laps_left

        if mode.by_fuel_per_lap:
            fuel_start = stint_len * pilot.fuel_push if pilot.fuel_push > 0 else 0.0
        else:
            # режим "кругов на баке" — всегда полный бак
            fuel_start = race.tank_liters

        stints.append(
            Stint(
                pilot=pilot.name,
                laps=stint_len,
                fuel_start=fuel_start,
                tyre_set=tyre_index + 1,
                eco=False,
            )
        )

        laps_left -= stint_len

    # Попытка убрать короткий финальный стинт  #todo бред (переписать)
    if len(stints) >= 3:
        last = stints[-1]
        if last.laps > 0 and last.laps < base_stint_len * 0.5:
            prev1 = stints[-2]
            prev2 = stints[-3]
            add1 = last.laps // 2
            add2 = last.laps - add1
            prev1.laps += add1
            prev2.laps += add2
            prev1.eco = True
            prev2.eco = True
            stints.pop()

    return stints


def compute_total_race_time_sec(
    race: RaceParams,
    pilots: List[Pilot],
    stints: List[Stint],
) -> float:
    """
    Время гонки = круги + пит-стопы + смены пилота.
    """
    if not stints or not pilots:
        return 0.0

    pilot_map = {p.name: p for p in pilots}

    total_lap_time = 0.0
    total_pit_time = 0.0

    prev_tyre_set = None
    prev_pilot_name = None

    for i, stint in enumerate(stints):
        pilot = pilot_map.get(stint.pilot)
        if not pilot:
            continue

        total_lap_time += stint.laps * pilot.lap_time_sec

        if i > 0:
            if stint.tyre_set == prev_tyre_set:
                total_pit_time += race.pit_refuel_sec
            else:
                total_pit_time += race.pit_tyre_sec

            if stint.pilot != prev_pilot_name:
                total_pit_time += race.driver_change_sec

        prev_tyre_set = stint.tyre_set
        prev_pilot_name = stint.pilot

    return total_lap_time + total_pit_time
