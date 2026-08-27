# Charts Tab

The charts tab contains the following:

**Options:** Controls the data shown in the plot area and the data table.

**Plot area:** Displays the selected parameter against either date/time or time since reconductoring. The plot area can be zoomed in and out, and the data can be downloaded as a CSV file.

**Data Availability Timeline**: Shows the availability of data for the selected sites over time.

**Data table:** Displays the underlying raw readings for the selected sites and filters - this is collapsed by default, press *Expand table* to view. Can be exported to CSV.


## Options

**Date Range**: Start and end date for the data to be displayed in the plot area and data table. The default is the all data.

**Condition:**: Wet or dry conductor conditions. The default is all conditions.

**Parameter**: The noise parameter to be plotted in the plot area and displayed in the data table. The default is Leq Adjusted.

**Aggregation period**: The time period over which the events are aggregated. The default is 2 weeks.

**Sample Rate**: The rate of data sampling from the noise logger. The default is 15-minutes. All current loggers are set to 15-minute sample rate, but the tool can handle data at 1-minute sample rates as well.

**Conductor and Treatment**: Type of conductor (Chukar, Goat, etc.). The default is all conductors and treatments.

**Grease**: Amount of conductor that is greased. The default is all. See below for more information on how grease is described.

**Detection Logic:** The logic used to detect noise events. The default is the *Updated 2026*, but the tool can also display data using the previous logic.

**Show historical**: By default all historical data is hidden, press this button to view.

**Sites panel:** Displays the sites that are available for selection. The default is all sites. Sites can be selected from a dropdown or deselected by clicking on the *x* beside the site name in the list.

## Chart

**Hover**: Hovering over a point will display the details of that point. 

**Hide/Show**: The legend can be used to hide or show a site by clicking on the site name in the legend.

**Axis Resizing**: The axes can be resized by clicking and dragging the axis labels. 

**Zoom**: The plot area can be zoomed in and out by clicking and dragging a box around the area of interest. To reset the zoom, click the *Reset Axis* button in the top right corner of the chart.

**Save as image:** The chart can be saved as an image by clicking the *Save as PNG* button in the top right corner of the chart.

## Adjust data series colour and style
The colour of each line in the chart can be changed using the "Plot colour" column on the Sites tab. All conductors for the site are presented as the same colour line.

You can select a different colour for historical data by using the "Historical line colour" column on the Sites tab. All historical data for the site are presented as the same colour line but is slightly transparent.

You can find a colour picker tool here: [https://www.w3schools.com/colors/colors_picker.asp](https://www.w3schools.com/colors/colors_picker.asp)

You can also change the line style for each reconductored site using the "Line style" column on the Reconductoring tab. Line style options include: 'solid', 'dot', 'dash', 'longdash', 'dashdot' and 'longdashdot'.


## Data Availability Timeline
This is a static chart and shows the availability of data for the selected sites over time. 


### Data Table
Pressing *Expand table* will display the underlying raw readings for the selected sites and filters. The data table can be exported to CSV by pressing the *Export CSV* button in the top right corner of the data table.
