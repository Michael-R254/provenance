---
id: example-rain-forecaster
title: Example Rain Forecaster
status: approved
version: 1
updated: 2026-02-01
type: coursework
permission: "fixture, not real"
summary: A fictional service that forecasts imaginary rainfall. Used only for evaluation tests.
skills: [time series forecasting]
languages: [Python, SQL]
frameworks: [ExampleBoost]
guardrails:
  - "The forecast comes from a gradient boosting regressor, not a neural network or deep learning model."
---

## Overview

The Example Rain Forecaster predicts next-day rainfall for imaginary towns from fictional sensor readings.

## Problem

The fictional town council needed earlier warnings to clear drains before heavy rain.

## My contributions

I built the feature pipeline, trained a gradient boosting model and wrote the evaluation notebook.

## Architecture

Sensor readings land in a queue, a nightly job aggregates them into features in Postgres, and a gradient boosting regressor produces the forecast.

## Challenges and decisions

Sensors often went offline, leaving gaps. I chose forward-filling for short gaps and dropping days with long gaps, and documented the trade-off.

## Limitations and what I would do next

The model ignores upstream weather systems. Next I would add regional radar features.
