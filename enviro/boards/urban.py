import time, math
from machine import Pin, ADC
from breakout_bme280 import BreakoutBME280
from pimoroni_i2c import PimoroniI2C
from phew import logging
from enviro import i2c
from ucollections import OrderedDict

# how long to capture the microphone signal for when taking a reading, in milliseconds
MIC_SAMPLE_TIME_MS = 500

sensor_reset_pin = Pin(9, Pin.OUT, value=True)
sensor_enable_pin = Pin(10, Pin.OUT, value=False)
boost_enable_pin = Pin(11, Pin.OUT, value=False)

noise_adc = ADC(0)

bme280 = BreakoutBME280(i2c, 0x77)

PM1_UGM3                = 2
PM2_5_UGM3              = 3
PM10_UGM3               = 4
PM1_UGM3_ATHMOSPHERIC   = 5
PM2_5_UGM3_ATHMOSPHERIC = 6
PM10_UGM3_ATHMOSPHERIC  = 7
PM0_3_PER_LITRE         = 8
PM0_5_PER_LITRE         = 9
PM1_PER_LITRE           = 10
PM2_5_PER_LITRE         = 11
PM5_PER_LITRE           = 12
PM10_PER_LITRE          = 13

def particulates(particulate_data, measure):
  # bit of a fudge to convert decilitres into litres... who uses decilitre?!
  multiplier = 10 if measure >= PM0_3_PER_LITRE else 1
  return ((particulate_data[measure * 2] << 8) | particulate_data[measure * 2 + 1]) * multiplier

def get_sensor_readings(seconds_since_last):
  i2c_devices = i2c.scan()
  data = OrderedDict()
  # bme280 returns the register contents immediately and then starts a new reading
  # we want the current reading so do a dummy read to discard register contents first
  bme280.read()
  time.sleep(0.1)
  bme280_data = bme280.read()
  data["temperature"] = round(bme280_data[0], 2)
  data["humidity"] = round(bme280_data[2], 2)
  data["pressure"] = round(bme280_data[1] / 100.0, 2)
  
  logging.debug("  - starting particulate sensor... will wait at least 5 seconds before reading")
  boost_enable_pin.value(True)
  sensor_enable_pin.value(True)

  # allow airflow to start
  # while doing that, take other sensors' measurements
  logging.debug("  - taking microphone reading")
  start = time.ticks_ms()
  min_value = 1.65
  max_value = 1.65
  while time.ticks_diff(time.ticks_ms(), start) < MIC_SAMPLE_TIME_MS:
    value = (noise_adc.read_u16() * 3.3) / 65535
    min_value = min(min_value, value)
    max_value = max(max_value, value)
  
  noise_vpp = max_value - min_value
  data["noise"] = round(noise_vpp, 3)

  # use data from SCD41 True-CO2 sensor if it's detected on the bus
  if 0x62 in i2c_devices:
    import breakout_scd41
    logging.debug("  - taking co2 reading")
    breakout_scd41.init(i2c)
    breakout_scd41.start()

    while not breakout_scd41.ready():
      time.sleep_ms(10)

    co2, temperature, humidity = breakout_scd41.measure()
    data["co2_ppm"] = co2
    data["temperature"] += temperature
    data["humidity"] += humidity
    data["temperature"] /= 2
    data["humidity"] /= 2

  while time.ticks_diff(time.ticks_ms(), start) < 5000:
    time.sleep_ms(10)
  logging.debug("  - taking pms5003i reading")
  # setup the i2c bus for the particulate sensor
  pms_i2c = PimoroniI2C(14, 15, 100000)
  particulate_data = pms_i2c.readfrom_mem(0x12, 0x00, 32)

  sensor_enable_pin.value(False)
  boost_enable_pin.value(False)

  data["pm1"] = particulates(particulate_data, PM1_UGM3), 
  data["pm2_5"] = particulates(particulate_data, PM2_5_UGM3), 
  data["pm10"] = particulates(particulate_data, PM10_UGM3)

  return data

