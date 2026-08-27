# General

The Conductor Noise Tool ingests  noise and weather readings from Jepsen monitoring sites, processes them into detected noise events, and presents the results across the tabs along the top of this page: Charts, Sites, Outages,
Reconductoring, Historical, Trends, Locations, and Weather.


## Read access
Users with read access can view the data and charts.
Users with write access can change alter values within the tables.


## New monitoring sites
New monitors installed and added to the 'noiseandweather.com' website will be automatically picked up by this reporting tool and filtered and displayed.

**A request must be made to Jepsen electronics (04 6357 7539) to add the new site(s) to the API.**


See the other sub-tabs here for details on a specific tab or feature.


## Data processing

The ingestion and processing of the data is done in a series of steps, at different time intervals, and is described in the following table.

| Operation | Description | Schedule |
| --- | --- | --- |
| Ingest raw readings | Pulls noise and weather readings via Jepsen API. Only new data is pulled. Processes data into detected noise events based on both detection logics. | Daily, 02:00 |
|Conductor Summary| Aggregates processed readings into one row per (site, detection_logic, measurement_duration_minutes) — mean/spread of the selected metric. Backs the Trends tab's "Conductor summary" box plot (one box per site, coloured by that site's current conductor type). | Daily, 02:40 |
| Rain-rate fits | Fits a logarithmic curve (metric = slope·ln(rain1) + intercept) per (site, detection_logic, metric), over wet/included/rain1>0 rows only, skipped if fewer than 3 qualifying points. Drawn as the dashed best-fit line on Trends' "Rain rate vs level" scatter chart, in the same colour as that site's markers. | Daily, 02:50 |
|Reconductoring age| Calculates the age of the current conductor per site, based on the most recent qualifying reconductoring event. Skipped if fewer than 3 qualifying points. | Daily, 02:55 |
|Conductor age fits|Fits a logarithmic curve (metric = slope·ln(reconductoring_age) + intercept) per (site, detection_logic, metric), over included rows with reconductoring age > 0 (log undefined at 0), skipped if fewer than 3 qualifying points. Drawn as the dashed best-fit line on Trends' "Age effects" chart. Must run after Reconductoring age, since it reads that column.|Daily, 03:05|
|Reading availability|Aggregates processed reading full, unfiltered history (min datetime, max datetime, row count) per site — deliberately never capped or date-filtered, unlike every chart query. Backs the Charts tab's "Data Availability Timeline" and the Locations tab's per-site "date range of available data". | Daily, 03:15 |
|Wind rose| Aggregates the raw reading table into 16 compass-sector wind statistics (sample count, average speed) per (site, year, month). Backs the Weather tab's wind rose chart; a selected date range re-aggregates a subset of these rows rather than re-querying reading. | Weekly, Sunday, 03:30 |
|Monthly rainfall| Aggregates raw reading into average and total rainfall per (site, year, month). Backs the Weather tab's monthly rainfall chart, same date-range re-aggregation approach as Wind rose. | Weekly, Sunday, 03:45 |
|Monthly weather stats|Aggregates raw reading into min/max/average rainfall and wind speed per (site, year, month). Backs the Weather tab's date-range "monthly rainfall/wind speed range" charts (shaded min-max band plus mean line). | Weekly, Sunday, 04:00 |