from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDoubleSpinBox, QSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QLabel, QTimeEdit,
    QRadioButton, QButtonGroup
)
from PyQt5.QtCore import QTime
from PyQt5.QtGui import QColor
from model import (
    plan_stints, RaceParams, TyreParams,
    _build_pilots, compute_total_race_time_sec, ConsumptionMode
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Race Strategy Calculator")

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        # ---------- Параметры гонки ----------
        race_form = QFormLayout()

        # Длительность гонки: часы и минуты
        self.race_time_edit = QTimeEdit()
        self.race_time_edit.setDisplayFormat("HH:mm")
        self.race_time_edit.setTime(QTime(2, 0))  # 2:00 по умолчанию

        self.tank = QDoubleSpinBox()
        self.tank.setSuffix(" л")
        self.tank.setDecimals(1)
        self.tank.setRange(0, 500)

        self.tyre_sets = QSpinBox()
        self.tyre_sets.setRange(1, 50)

        # Кол-во пилотов
        self.pilot_count_spin = QSpinBox()
        self.pilot_count_spin.setRange(1, 10)
        self.pilot_count_spin.setValue(3)
        self.pilot_count_spin.valueChanged.connect(self._on_pilot_count_changed)

        # Время пит-стопов: минуты и секунды
        self.pit_refuel_time = QTimeEdit()
        self.pit_refuel_time.setDisplayFormat("mm:ss")
        self.pit_refuel_time.setTime(QTime(0, 0, 30))  # 00:30

        self.pit_tyre_time = QTimeEdit()
        self.pit_tyre_time.setDisplayFormat("mm:ss")
        self.pit_tyre_time.setTime(QTime(0, 0, 40))    # 00:40

        # Время смены пилота
        self.driver_change_time = QTimeEdit()
        self.driver_change_time.setDisplayFormat("mm:ss")
        self.driver_change_time.setTime(QTime(0, 0, 10))  # 00:10

        race_form.addRow("Длительность гонки (ч:мин)", self.race_time_edit)
        race_form.addRow("Объём бака", self.tank)
        race_form.addRow("Кол-во комплектов шин", self.tyre_sets)
        race_form.addRow("Кол-во пилотов", self.pilot_count_spin)
        race_form.addRow("Пит-стоп дозаправка (м:с)", self.pit_refuel_time)
        race_form.addRow("Пит-стоп со сменой резины (м:с)", self.pit_tyre_time)
        race_form.addRow("Смена пилота (м:с)", self.driver_change_time)

        main_layout.addLayout(race_form)

        # ---------- Режим ввода расхода ----------
        mode_layout = QHBoxLayout()
        self.rb_mode_fuel = QRadioButton("Расход на круг (л/круг)")
        self.rb_mode_laps = QRadioButton("Кругов на баке")
        self.rb_mode_laps.setChecked(True)  # по умолчанию "кругов на баке"

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_mode_fuel, 0)
        self.mode_group.addButton(self.rb_mode_laps, 1)
        self.mode_group.buttonClicked.connect(self._on_mode_changed)

        mode_layout.addWidget(self.rb_mode_fuel)
        mode_layout.addWidget(self.rb_mode_laps)
        main_layout.addLayout(mode_layout)

        # ---------- Таблица пилотов ----------
        # 0 Имя
        # 1 Время круга
        # 2 Push, л/круг
        # 3 Eco, л/круг
        # 4 Push, кругов/бак
        # 5 Eco, кругов/бак
        self.pilot_table = QTableWidget(0, 6)
        self.pilot_table.setHorizontalHeaderLabels(
            [
                "Пилот",
                "Время круга (мм:сс.с)",
                "Push, л/круг",
                "Eco, л/круг",
                "Push, кругов/бак",
                "Eco, кругов/бак",
            ]
        )
        self.pilot_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.pilot_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.pilot_table.setDragDropMode(QAbstractItemView.InternalMove)
        self.pilot_table.setDragDropOverwriteMode(False)

        main_layout.addWidget(self.pilot_table)

        self._add_demo_pilots()
        self._on_mode_changed()  # скрыть/показать колонки под дефолтный режим

        # ---------- Кнопка расчёта ----------
        buttons_layout = QHBoxLayout()
        self.calc_btn = QPushButton("Рассчитать стратегию")
        self.calc_btn.clicked.connect(self.on_calc_clicked)
        buttons_layout.addWidget(self.calc_btn)
        main_layout.addLayout(buttons_layout)

        # ---------- Таблица результата стинтов ----------
        self.stints_table = QTableWidget(0, 4)
        self.stints_table.setHorizontalHeaderLabels(
            ["Пилот", "Круги в стинте", "Стартовое топливо, л", "Комплект шин"]
        )
        main_layout.addWidget(self.stints_table)

        # ---------- Итоговое время гонки ----------
        self.total_time_label = QLabel("Итоговое время гонки: —")
        main_layout.addWidget(self.total_time_label)

    # ---------- Пилоты ----------

    def _add_demo_pilots(self):
        self.pilot_table.setRowCount(0)
        names = ["Пилот A", "Пилот B", "Пилот C", "Пилот D", "Пилот E"]
        for i in range(self.pilot_count_spin.value()):
            name = names[i] if i < len(names) else f"Пилот {i+1}"
            self._add_pilot_row(name, "02:01.0", 2.8 + 0.1 * i, 2.5 + 0.1 * i, 36.0, 37.0)

    def _add_pilot_row(self, name, lap_time_str, fuel_push, fuel_eco, laps_push, laps_eco):
        row = self.pilot_table.rowCount()
        self.pilot_table.insertRow(row)
        self.pilot_table.setItem(row, 0, QTableWidgetItem(str(name)))
        self.pilot_table.setItem(row, 1, QTableWidgetItem(str(lap_time_str)))
        self.pilot_table.setItem(row, 2, QTableWidgetItem(str(fuel_push)))
        self.pilot_table.setItem(row, 3, QTableWidgetItem(str(fuel_eco)))
        self.pilot_table.setItem(row, 4, QTableWidgetItem(str(laps_push)))
        self.pilot_table.setItem(row, 5, QTableWidgetItem(str(laps_eco)))

    def _on_pilot_count_changed(self, new_count: int):
        current_rows = self.pilot_table.rowCount()

        if new_count < current_rows:
            for _ in range(current_rows - new_count):
                self.pilot_table.removeRow(self.pilot_table.rowCount() - 1)
            return

        if new_count > current_rows:
            start_index = current_rows
            names = ["Пилот A", "Пилот B", "Пилот C", "Пилот D", "Пилот E", "Пилот F"]
            for i in range(start_index, new_count):
                name = names[i] if i < len(names) else f"Пилот {i+1}"
                self._add_pilot_row(name, "02:01.0", 3.0, 2.7, 36.0, 37.0)

    # ---------- Режим ввода расхода ----------

    def _on_mode_changed(self):
        """Скрываем/показываем колонки расхода в зависимости от режима."""
        by_fuel = self.rb_mode_fuel.isChecked()

        # Режим "расход на круг": показываем 2-3, скрываем 4-5
        self.pilot_table.setColumnHidden(2, not by_fuel)
        self.pilot_table.setColumnHidden(3, not by_fuel)
        self.pilot_table.setColumnHidden(4, by_fuel)
        self.pilot_table.setColumnHidden(5, by_fuel)

    # ---------- Парсинг времени круга ----------

    def _parse_lap_time(self, text: str) -> float:
        """
        Ожидает строку вида 'MM:SS.s' или 'M:SS' и возвращает секунды.
        """
        text = text.strip()
        if not text:
            return 0.0
        try:
            parts = text.split(":")
            if len(parts) != 2:
                return float(text)
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60.0 + seconds
        except ValueError:
            return 0.0

    def _read_pilots(self):
        """
        Возвращает:
          pilots: List[(name, lap_time_sec, fuel_push, fuel_eco, laps_push, laps_eco)]
          avg_lap: среднее по lap_time_sec
        """
        pilots = []
        lap_times = []

        for row in range(self.pilot_table.rowCount()):
            items = [self.pilot_table.item(row, col) for col in range(6)]
            if not items[0] or not items[1]:
                continue

            name = items[0].text()
            lap_time_sec = self._parse_lap_time(items[1].text())

            fuel_push = float(items[2].text()) if items[2] else 0.0
            fuel_eco = float(items[3].text()) if items[3] else 0.0
            laps_push = float(items[4].text()) if items[4] else 0.0
            laps_eco = float(items[5].text()) if items[5] else 0.0

            lap_times.append(lap_time_sec)
            pilots.append((name, lap_time_sec, fuel_push, fuel_eco, laps_push, laps_eco))

        avg_lap = sum(lap_times) / len(lap_times) if lap_times else 0.0
        return pilots, avg_lap

    # ---------- Вспомогательные конвертеры времени ----------

    def _race_duration_hours(self) -> float:
        t: QTime = self.race_time_edit.time()
        total_minutes = t.hour() * 60 + t.minute()
        return total_minutes / 60.0

    def _time_to_seconds(self, t: QTime) -> float:
        return t.minute() * 60.0 + t.second()

    def _current_consumption_mode(self) -> ConsumptionMode:
        by_fuel = self.rb_mode_fuel.isChecked()
        return ConsumptionMode(by_fuel_per_lap=by_fuel)

    # ---------- Расчёт ----------

    def on_calc_clicked(self):
        pilots_tuples, avg_lap = self._read_pilots()
        if not pilots_tuples or avg_lap <= 0:
            return

        race = RaceParams(
            duration_hours=self._race_duration_hours(),
            avg_lap_sec=avg_lap,
            tank_liters=self.tank.value(),
            pit_refuel_sec=self._time_to_seconds(self.pit_refuel_time.time()),
            pit_tyre_sec=self._time_to_seconds(self.pit_tyre_time.time()),
            driver_change_sec=self._time_to_seconds(self.driver_change_time.time()),
        )
        tyre = TyreParams(
            sets=self.tyre_sets.value(),
        )

        mode = self._current_consumption_mode()

        stints = plan_stints(race, tyre, pilots_tuples, mode)
        self._show_stints(stints)

        pilots = _build_pilots(pilots_tuples)
        total_time_sec = compute_total_race_time_sec(race, pilots, stints)

        hours = int(total_time_sec // 3600)
        minutes = int((total_time_sec % 3600) // 60)
        seconds = int(total_time_sec % 60)
        race_time_str = f"{hours:d}:{minutes:02d}:{seconds:02d}"

        self.total_time_label.setText(f"Итоговое время гонки: {race_time_str}")
        self.setWindowTitle(f"Race Strategy Calculator — {race_time_str}")

    # ---------- Отображение стинтов ----------

    def _show_stints(self, stints):
        self.stints_table.setRowCount(0)
        for stint in stints:
            row = self.stints_table.rowCount()
            self.stints_table.insertRow(row)
            self.stints_table.setItem(row, 0, QTableWidgetItem(stint.pilot))
            self.stints_table.setItem(row, 1, QTableWidgetItem(str(stint.laps)))
            self.stints_table.setItem(row, 2, QTableWidgetItem(f"{stint.fuel_start:.1f}"))
            self.stints_table.setItem(row, 3, QTableWidgetItem(str(stint.tyre_set)))

            if getattr(stint, "eco", False):
                color = QColor(200, 255, 200)
                for col in range(4):
                    item = self.stints_table.item(row, col)
                    if item:
                        item.setBackground(color)
