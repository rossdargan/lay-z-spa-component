"""The Lay-Z Spa integration."""
import asyncio
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


from layz_spa.spa import Spa
from layz_spa.errors import InvalidPasswordOrEmail

from .const import CONF_API, CONF_DID, COORDINATOR, DOMAIN, HUB
from datetime import timedelta
import async_timeout
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["water_heater"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Lay-Z Spa component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Lay-Z Spa from a config entry."""
    hub = Spa(entry.data[CONF_API], entry.data[CONF_DID])
    await hub.update_status()
    _LOGGER.warning("temp %s", hub.temp_now)
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id][HUB] = hub
    hass.data[DOMAIN][entry.entry_id][CONF_NAME] = entry.data[CONF_NAME]
    hass.data[DOMAIN][entry.entry_id][CONF_DID] = entry.data[CONF_DID]

    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                return await hub.update_status()
        except InvalidPasswordOrEmail as err:
            raise UpdateFailed(f"The password or email address is invalid: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="lay-z sensor updater",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=60),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
