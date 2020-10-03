from calendar import timegm
from datetime import datetime
from os import (
    makedirs,
    path,
    walk,
)

import homematicip
import rrdtool
from flask import current_app as app
from homematicip.device import (
    ShutterContact,
    TemperatureHumiditySensorOutdoor,
    WallMountedThermostatPro,
)
from homematicip.home import Home


class HmIP(object):
    def __init__(self):
        config = homematicip.load_config_file(config_file=path.join(app.instance_path, 'config.ini'))
        self.home = Home()
        self.home.set_auth_token(config.auth_token)
        self.home.init(config.access_point)
        self.home.get_current_state()

    def fetch_metrics(self):
        try:
            self.home.get_current_state()
        except Exception as e:
            app.logger.error(repr(e))
        for group in self.home.groups:
            if group.groupType == 'META':
                for device in group.devices:
                    if isinstance(device, WallMountedThermostatPro):
                        self.__collect_thermostat_metrics(group.label, device)
                    elif isinstance(device, ShutterContact):
                        self.__collect_shutter_metrics(group.label, device)
                    elif isinstance(device, TemperatureHumiditySensorOutdoor):
                        self.__collect_thermostat_outdoor_metrics(group.label, device)

    def __collect_shutter_metrics(self, room, device):
        rrd = path.join(app.instance_path, 'rrds', room, f'{device.label}.rrd')
        if not path.exists(rrd):
            makedirs(path.join(app.instance_path, 'rrds', room), mode=0o0750, exist_ok=True)
            rrdtool.create(rrd, '--start', 'now', '--step', '180', 'DS:state:GAUGE:540:0:1', 'RRA:AVERAGE:0.5:1:360000')
        rrdtool.update(path.join(app.instance_path, 'rrds', room, f'{device.label}.rrd'), f'N: {self.__window_state(device.windowState)}')
        app.logger.debug('room: {}, label: {}, windowState: {}'.format(room, device.label, device.windowState))

    @staticmethod
    def __collect_thermostat_metrics(room, device):
        rrd = path.join(app.instance_path, 'rrds', room, f'{device.label}.rrd')
        if not path.exists(rrd):
            makedirs(path.join(app.instance_path, 'rrds', room), mode=0o0750, exist_ok=True)
            rrdtool.create(rrd, '--start', 'now', '--step', '180', 'DS:actualtemperature:GAUGE:540:0:50',
                           'DS:settemperature:GAUGE:540:0:40', 'DS:humidity:GAUGE:540:0:100', 'DS:vapor:GAUGE:540:0:100',
                           'RRA:AVERAGE:0.5:1:360000')
        rrdtool.update(path.join(app.instance_path, 'rrds', room, f'{device.label}.rrd'), f'N: {device.actualTemperature}:'
                                                                                          f'{device.setPointTemperature}:'
                                                                                          f'{device.humidity}:{device.vaporAmount}')
        app.logger.debug(f'room: {room}, label: {device.label}, temperature_actual: {device.actualTemperature}, temperature_setpoint: '
                         f'{device.setPointTemperature}, humidity_actual: {device.humidity} vaporAmount: {device.vaporAmount}')

    @staticmethod
    def __collect_thermostat_outdoor_metrics(room, device):
        rrd = path.join(app.instance_path, 'rrds', room, f'{device.label}.rrd')
        if not path.exists(rrd):
            makedirs(path.join(app.instance_path, 'rrds', room), mode=0o0750, exist_ok=True)
            rrdtool.create(rrd, '--start', 'now', '--step', '180', 'DS:actualtemperature:GAUGE:540:-20:55', 'DS:humidity:GAUGE:540:0:100',
                           'DS:vapor:GAUGE:540:0:100', 'RRA:AVERAGE:0.5:1:360000')
        rrdtool.update(path.join(app.instance_path, 'rrds', room, f'{device.label}.rrd'), f'N: {device.actualTemperature}:'
                                                                                          f'{device.humidity}:{device.vaporAmount}')
        app.logger.debug(
            f'room: {room}, label: {device.label}, temperature_actual: {device.actualTemperature}, humidity_actual: {device.humidity} '
            f'vaporAmount: {device.vaporAmount}')

    @staticmethod
    def __window_state(state):
        return 1 if state == 'OPEN' else 0

    def convert_to_time_ms(self, timestamp):
        return 1000 * self.convert_to_time_s(timestamp)

    @staticmethod
    def convert_to_time_s(timestamp):
        return timegm(datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%fZ').timetuple())

    def get_metric_names(self):
        ret = set()
        for group in self.home.groups:
            if group.groupType == 'META':
                for device in group.devices:
                    if isinstance(device, WallMountedThermostatPro):
                        ret.add('actualtemperature')
                        ret.add('settemperature')
                        ret.add('humidity')
                        ret.add('vapor')
                    elif isinstance(device, ShutterContact):
                        ret.add('state')
                    elif isinstance(device, TemperatureHumiditySensorOutdoor):
                        ret.add('actualtemperature')
                        ret.add('humidity')
                        ret.add('vapor')
        return ret

    def get_metrics(self, start, end, resolution, metrics):
        ret = []
        m = {}
        for root, dirs, files in walk(path.join(app.instance_path, 'rrds')):
            for file in files:
                if file.endswith('.rrd'):
                    rrd = path.join(root, file)
                    app.logger.debug(f'open rrd: {rrd}')
                    fetch = rrdtool.fetch(rrd, 'AVERAGE', '--resolution', resolution, '--start', str(self.convert_to_time_s(start)),
                                          '--end', str(self.convert_to_time_s(end)))
                    for num, name in enumerate(fetch[1]):
                        if name in metrics:
                            datapoints = []
                            ts = fetch[0][0]
                            for dp in fetch[2]:
                                datapoints.append([dp[num], ts * 1000])
                                ts += fetch[0][2]
                            ret.append({
                                'target': file.split('.')[0],
                                'datapoints': datapoints
                            })
        return ret
