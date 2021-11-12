import math
import collections
import pandas as pd

from dataclasses import dataclass, asdict
from pynverse import inversefunc
from pprint import pprint

# -----
# from Dr. Schulz's code
# https://github.com/ErichBSchulz/lung/blob/master/ventos/lung.py
# https://github.com/ErichBSchulz/lung/blob/master/ventos/sim/simple.py

# a set of three bi-directional lung and chest wall curves allowing calculation
# of pressure from volume, and volume from pressure
# exports both simple and vectorized forms

# see https://docs.google.com/spreadsheets/d/1BO59dnA8dqs8TdPTD3WMBnii7FRxPDB1FVFzTB6eVsU/edit?usp=sharing for curves


def lung(p):
    return 6.66 + 27.9 * math.log(p if p > 0 else 0.000000001)


def chest_wall(p):
    return 51.3 * math.exp(0.0635 * p)


def total(p):
    b = 46.2134
    a = -261.437
    c = -9.68139
    d = 11.6401
    f = 1.2952
    return b + c * math.sin((p+a)/d) + f * p


switch_v_p = {"Total": total,
              "Lung": lung,
              "Chest": chest_wall}
switch_p_v = {"Total": inversefunc(total),
              "Lung": inversefunc(lung),
              "Chest": inversefunc(chest_wall)}


def asscalar(x):
    is_list = hasattr(x, "item")  # isinstance(x, list)
    return x.item() if is_list else x


# report volumes as % of total TLC
def volume_from_pressure(p, type="Total"):
    func = switch_v_p.get(type, lambda: 'error bad type')
    return asscalar(func(p))


def pressure_from_volume(v, type="Total"):
    func = switch_p_v.get(type, lambda: 'error bad type')
    return asscalar(func(v))


# setting up Patient
Patient_log = collections.namedtuple(
    'Patient_log',
    ['time', 'pressure_mouth', 'pressure_alveolus', 'pressure_intrapleural', 'lung_volume', 'flow'])


class Patient:
    def __init__(self,
                 height=175,  # cm
                 weight=70,  # kg
                 sex='M',  # M or other
                 pressure_mouth=0,  # cmH2O
                 resistance=10  # cmh2o/l/s or cmh2o per ml/ms
                 ):
        self.time = 0  # miliseconds
        self.height = height
        self.weight = weight
        self.sex = sex
        self.TLC = 6000 if sex == 'M' else 4200  # todo calculate on age, height weight
        self.pressure_mouth = pressure_mouth
        self.resistance = resistance
        self.pressure_alveolus = pressure_mouth  # start at equlibrium
        v_percent = volume_from_pressure(
            self.pressure_alveolus, 'Total')  # assuming no resp effort
        self.lung_volume = self.TLC * v_percent / 100
        self.pressure_intrapleural = pressure_from_volume(v_percent, 'Chest')
        self.flow = 0
        self.log = []

    def status(self):
        return Patient_log(self.time, self.pressure_mouth, self.pressure_alveolus, self.pressure_intrapleural, self.lung_volume, self.flow)

    def advance(self, advance_time=200, pressure_mouth=0):
        self.time = self.time + advance_time  # miliseconds
        self.pressure_mouth = pressure_mouth
        gradient = pressure_mouth - self.pressure_alveolus
        self.flow = gradient / self.resistance  # l/second or ml/ms
        self.lung_volume += self.flow * advance_time
        v_percent = self.lung_volume * 100 / self.TLC
        self.pressure_alveolus = pressure_from_volume(v_percent, "Total")
        self.pressure_intrapleural = pressure_from_volume(v_percent, "Chest")
        status = self.status()
        self.log.append(status)
        return status


# setting up Ventilator
Ventilator_log = collections.namedtuple(
    'Ventilator_log', ['time', 'phase', 'pressure', 'pressure_mouth'])


class Ventilator:
    def __init__(self, mode="PCV", Pi=15, PEEP=5, rate=10, IE=0.5):
        self.pressure = 0
        self.pressure_mouth = 0
        self.mode = mode
        self.Pi = Pi
        self.PEEP = PEEP
        self.rate = rate
        self.IE = IE
        self.phase = "E"
        self.log = []
        self.time = 0  # miliseconds

    def target_pressure(self):
        return self.PEEP if self.phase == "E" else self.Pi

    def status(self):
        return Ventilator_log(self.time, self.phase, self.pressure, self.pressure_mouth)

    def advance(self, advance_time=200, pressure_mouth=0):
        self.time = self.time + advance_time  # miliseconds
        self.pressure_mouth = pressure_mouth  # cmH2O
        # set phase
        breath_length = 60000 / self.rate  # milliseconds
        time_since_inspiration_began = self.time % breath_length
        inspiration_length = breath_length * self.IE / (self.IE + 1)
        new_phase = "I" if time_since_inspiration_began < inspiration_length else "E"
        if new_phase != self.phase:
            self.phase = new_phase
            self.pressure = self.target_pressure()
            self.pressure_mouth = self.pressure  # assume perfect ventilator
        status = self.status()
        self.log.append(status)
        return status


def loop(patient, ventilator,
         start_time=0, end_time=20000, time_resolution=50, events=[]):
    # print('starting', patient.status())
    patient_status = patient.advance(advance_time=0)
    # print('vent starting', ventilator.status())
    for current_time in range(start_time, end_time, time_resolution):
        ventilator_status = ventilator.advance(
            advance_time=time_resolution, pressure_mouth=patient_status.pressure_mouth)
        patient_status = patient.advance(
            advance_time=time_resolution, pressure_mouth=ventilator_status.pressure_mouth)

        # if len(events) and events[0]['time']*1000 <= current_time:
        #     e = events.pop(0)
        #     print(
        #         f'Event at {current_time}ms setting {e["attr"]} to {e["val"]}')
        #     setattr(ventilator, e["attr"], e["val"])

    df = pd.DataFrame.from_records(patient.log, columns=Patient_log._fields)

    # if len(events):
    #     print(f'WARNING {len(events)} unprocessed')

    return df


# excecute a scenario (s)
# returns a dataframe
def execute_scenario(s):
    # print("FROM EXECUTE SCENARIO")
    # pprint(s)
    p = Patient(resistance=s['resistance'], pressure_mouth=s['PEEP'])
    v = Ventilator(PEEP=s['PEEP'], rate=s['rate'], IE=s['IE'], Pi=s['Pi'])
    pdf = loop(p, v,
               end_time=s['end_time'] * 1000, time_resolution=s['time_resolution'],
               events=s['events'])
    # decorate_sim(pdf, s)
    return pdf


litres_per_second_to_ml_per_minute = 60*1000


def df_to_PIRDS(df):
    pirds = []
    for index, r in df.iterrows():
        pirds.append({"event": "M",
                      "type": "P", "loc": "I",
                      "ms": int(r.time), "val": int(round(r.pressure_mouth))})
        # pirds.append({"event": "M",
        #               "type": "P", "loc": "E",
        #               "ms": int(r.time), "val": int(round(r.pressure_2))})
        pirds.append({"event": "M",
                      "type": "F", "loc": "I",
                      "ms": int(r.time), "val": int(round(r.flow * litres_per_second_to_ml_per_minute))})
        # pirds.append({"event": "M",
        #               "type": "F", "loc": "E",
        #               "ms": int(r.time), "val": int(round(r.flow_e * litres_per_second_to_ml_per_minute))})
    # return pd.DataFrame.from_records(pirds)
    return pirds
