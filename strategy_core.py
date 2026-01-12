from dataclasses import dataclass
from typing import List, Literal


Mode = Literal["push", "eco"]


@dataclass
class PilotSimple:
    name: str
    lap_time_sec: float          # среднее время круга, сек
    laps_push: int               # кругов на баке (push)
    laps_eco: int                # кругов на баке (eco)


@dataclass
class RaceSimple:
    total_laps: int
    pit_refuel_sec: float
    pit_tyre_sec: float
    driver_change_sec: float


@dataclass
class TyreSimple:
    sets: int                    # количество комплектов шин


@dataclass
class StintSimple:
    pilot: str
    laps: int
    tyre_set: int                # 1..N
    mode: Mode                   # "push" или "eco"


def _assign_tyres_simple(num_stints: int, tyre: TyreSimple) -> List[int]:
    """2 стинта на комплект, при нехватке часть комплектов по 3 стинта."""
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


def build_stints_iterative_with_pilots(
    race: RaceSimple,
    tyre: TyreSimple,
    pilots: List[PilotSimple],
) -> List[StintSimple]:
    """
    Итеративный расчёт:
      1) считаем N стинтов по push (по первому пилоту);
      2) делаем N push-стинтов;
      3) если кругов не хватает — по одному переводим стинты в eco (увеличивая laps),
         пока не дойдём до all-eco или не покроем гонку;
      4) если all-eco всё ещё не хватает — возвращаемся к all-push и добавляем ещё один стинт;
      5) последний стинт при необходимости укорачиваем, чтобы ровно закрыть total_laps.
    Пилоты закреплены за комплектами шин по порядку.
    """
    if not pilots:
        return []

    p0 = pilots[0]
    laps_push = p0.laps_push
    laps_eco = p0.laps_eco
    if laps_push <= 0 or laps_eco < laps_push:
        raise ValueError("Некорректные параметры стинта")

    total_laps = race.total_laps

    # шаг 1: количество push-стинтов
    n_push = (total_laps + laps_push - 1) // laps_push

    # функция, считающая суммарные круги
    def total_laps_now(sts: List[StintSimple]) -> int:
        return sum(s.laps for s in sts)

    # шаг 2: начальный план — все push
    stints = [StintSimple(pilot="", laps=laps_push, tyre_set=0, mode="push") for _ in range(n_push)]

    # распределяем шины и пилотов (один пилот на комплект)
    tyre_indices = _assign_tyres_simple(n_push, tyre)
    sets = max(tyre.sets, 1)
    set_to_pilot = {}
    for tyre_index in range(sets):
        set_to_pilot[tyre_index] = pilots[tyre_index % len(pilots)]

    for i, s in enumerate(stints):
        t_index = tyre_indices[i]
        pilot = set_to_pilot[t_index]
        s.tyre_set = t_index + 1
        s.pilot = pilot.name

    # шаг 3: итеративно переводим стинты в eco
    idx = 0
    while total_laps_now(stints) < total_laps and idx < len(stints):
        s = stints[idx]
        if s.mode == "push":
            delta = laps_eco - laps_push
            if delta > 0:
                s.mode = "eco"
                s.laps += delta
        idx += 1

    # шаг 4: если даже all-eco не покрывает гонку — всё в push + ещё один стинт
    if total_laps_now(stints) < total_laps:
        stints = [
            StintSimple(
                pilot="",
                laps=laps_push,
                tyre_set=0,
                mode="push",
            )
            for _ in range(n_push + 1)
        ]
        tyre_indices = _assign_tyres_simple(len(stints), tyre)
        for i, s in enumerate(stints):
            t_index = tyre_indices[i]
            pilot = set_to_pilot[t_index]
            s.tyre_set = t_index + 1
            s.pilot = pilot.name

    # шаг 5: подрезаем последний стинт, чтобы ровно попасть в total_laps
    extra = total_laps_now(stints) - total_laps
    if extra > 0:
        last = stints[-1]
        last.laps = max(last.laps - extra, 1)

    return stints


if __name__ == "__main__":
    # Пример, похожий на твой кейс
    pilots = [
        PilotSimple("Пилот A", lap_time_sec=121.0, laps_push=36, laps_eco=37),
        PilotSimple("Пилот B", lap_time_sec=121.0, laps_push=35, laps_eco=36),
        PilotSimple("Пилот C", lap_time_sec=121.0, laps_push=36, laps_eco=37),
    ]
    total_laps = 180  # сюда подставишь своё число кругов
    race = RaceSimple(
        total_laps=total_laps,
        pit_refuel_sec=30.0,
        pit_tyre_sec=40.0,
        driver_change_sec=10.0,
    )
    tyre = TyreSimple(sets=4)

    stints = build_stints_iterative_with_pilots(race, tyre, pilots)
    print("стинтов:", len(stints), "кругов:", sum(s.laps for s in stints))
    for i, s in enumerate(stints, 1):
        print(i, s.pilot, s.mode, s.laps, "кругов, комплект", s.tyre_set)
