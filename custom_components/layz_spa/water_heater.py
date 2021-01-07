from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import logging
from homeassistant.helpers.config_validation import string
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    PRECISION_WHOLE,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from typing import Optional
from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_OPERATION_LIST,
    ATTR_OPERATION_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.util.temperature import convert as convert_temperature
from layz_spa.spa import Spa
from .const import CONF_DID, COORDINATOR, DOMAIN, HUB, ATTR_AWAY_MODE

DEFAULT_MIN_TEMP = 0
DEFAULT_MAX_TEMP = 40
ENTITY_ID_FORMAT = DOMAIN + ".{}"

ICON = "mdi:hot-tub"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up a config entry."""
    title = hass.data[DOMAIN][entry.entry_id][CONF_NAME]
    deviceid = hass.data[DOMAIN][entry.entry_id][CONF_DID]
    spa = hass.data[DOMAIN][entry.entry_id][HUB]
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    heater = SpaWaterHeater(spa, title, deviceid, coordinator)
    async_add_devices([heater])


class SpaWaterHeater(WaterHeaterEntity):
    def __init__(
        self, spa: Spa, title: string, deviceid: string, observer: DataUpdateCoordinator
    ) -> None:
        """Initialize the water_heater device."""
        self.spa = spa
        self.title = title
        self.deviceid = deviceid
        self._supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_AWAY_MODE
        self.observer = observer

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(self.observer.async_add_listener(self._update_callback))
        self.async_on_remove(self.observer.async_add_listener(self._update_callback))
        self._update_callback()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self.async_write_ha_state()

    # @property
    # def operation_list(self) -> List[str]:
    #     """Return the list of available operation modes."""
    #     return list(HA_OPMODE_TO_GH)

    # @property
    # def current_operation(self) -> str:
    #     """Return the current operation mode."""
    #     return GH_STATE_TO_HA[self._zone.data["mode"]]

    # async def async_set_operation_mode(self, operation_mode) -> None:
    #     """Set a new operation mode for this boiler."""
    #     await self._zone.set_mode(HA_OPMODE_TO_GH[operation_mode])
    @property
    def state(self):
        """Return the current state."""
        return show_temp(
            self.hass,
            self.spa.temp_now,
            self.temperature_unit,
            self.precision,
        )

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        supported_features = self.supported_features or 0

        data = {
            ATTR_MIN_TEMP: show_temp(
                self.hass, self.min_temp, self.temperature_unit, self.precision
            ),
            ATTR_MAX_TEMP: show_temp(
                self.hass, self.max_temp, self.temperature_unit, self.precision
            ),
        }

        if supported_features & SUPPORT_OPERATION_MODE:
            data[ATTR_OPERATION_LIST] = self.operation_list

        if supported_features & SUPPORT_AWAY_MODE:
            is_away = self.is_away_mode_on
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        return data

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {
            ATTR_CURRENT_TEMPERATURE: show_temp(
                self.hass,
                self.current_temperature,
                self.temperature_unit,
                self.precision,
            ),
            ATTR_TEMPERATURE: show_temp(
                self.hass,
                self.target_temperature,
                self.temperature_unit,
                self.precision,
            ),
            "Heat Power": self.spa.heat_power,
            "Power": self.spa.power,
            "Bubbles Power": self.spa.wave_power,
            "Filter Power": self.spa.filter_power,
        }

        supported_features = self.supported_features

        if supported_features & SUPPORT_OPERATION_MODE:
            data[ATTR_OPERATION_MODE] = self.current_operation

        if supported_features & SUPPORT_AWAY_MODE:
            is_away = self.is_away_mode_on
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        return data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.title

    @property
    def unique_id(self) -> Optional[str]:
        """Return unique id for the entity."""
        return ENTITY_ID_FORMAT.format(self.deviceid)

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return ICON

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self.spa.temp_now

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self.spa.temp_set

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(
            DEFAULT_MIN_TEMP, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(
            DEFAULT_MAX_TEMP, TEMP_CELSIUS, self.temperature_unit
        )

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS if self.spa.temp_set_unit == "°C" else TEMP_FAHRENHEIT

    @property
    def supported_features(self) -> int:
        """Return the bitmask of supported features."""
        return self._supported_features

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperature for this zone."""
        await self.spa.set_target_temperature(int(kwargs[ATTR_TEMPERATURE]))

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return not (self.spa.power & self.spa.heat_power)

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        _LOGGER.warning("Turning Away mode on")
        await self.spa.set_heat_power(False)

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        _LOGGER.warning("Turning on heat")
        if not (self.spa.power):
            _LOGGER.warning("Turning on power")
            await self.spa.set_power(True)
        await self.spa.set_heat_power(True)
