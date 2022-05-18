# Serial Data Visualisation Tool
[![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/)
[![Last Commit](https://img.shields.io/badge/last%20commit-may%202022-orange)]()
> A GUI for visualising serial data in real-time

<br/>
<p align="left">

## Table of Contents

- [General Info](#general-information) <br/>
- [Technologies Used](#technologies-used) <br/>
- [Contact](#contact)

</p> 
<br/>

## General Information
This repository contains the source code of the data visualisation tool. The data visualisation tool runs locally and
makes use of dedicated GPUs and multicore CPUs for increased performance. Currently, the tool supports data from 
serial COM protocols.

Functionalities of the tool are live heatmap visualisation, live plot visualisations and CSV data logging.

<br/>

## Technologies Used
### Backtesting
For testing the strategy on historical data with tools optimised for faster calculations on datasets. For example OHLC 
charts on minute intervals over months and years.

| Language     | GUI Framework | Data Visualisation   |
|--------------|---------------|----------------------|
| Python 3.7.6 | Pyqt5         | Vispy <br/>Pyqtgraph |

