# Data Source & Attribution

This integration retrieves avalanche bulletin and warning-region data at runtime from the public API of the **WSL Institute for Snow and Avalanche Research SLF** (`aws.slf.ch`).

That data is licensed under **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**, separately from this repository's MIT-licensed source code. The license requires a clearly visible reference to the data source whenever the data is displayed, processed, or otherwise used.

**Required attribution:** *WSL Institute for Snow and Avalanche Research SLF*

This integration fulfills that requirement by setting the `attribution` attribute (`"Data: WSL Institute for Snow and Avalanche Research SLF (CC BY 4.0)"`) on every sensor entity it creates, which Home Assistant surfaces in the entity's "More Info" dialog. If you build dashboards, automations, or republish this data elsewhere, please keep that attribution visible or add your own equivalent notice.

This integration is unofficial and not affiliated with, endorsed by, or supported by the SLF. It only reads their published open data.

Official SLF data service: https://www.slf.ch/en/services-and-products/slf-data-service/
