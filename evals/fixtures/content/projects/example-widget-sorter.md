---
id: example-widget-sorter
title: Example Widget Sorter
status: approved
version: 1
updated: 2026-01-15
type: personal
permission: "fixture, not real"
summary: A fictional tool that sorts imaginary widgets by colour. Used only for evaluation tests.
skills: [computer vision]
languages: [Python]
frameworks: [ExampleVision]
---

<!-- Evaluation fixture. Every statement is invented. -->

## Overview

The Example Widget Sorter is a fictional tool that photographs imaginary widgets on a conveyor and sorts them by colour.

## Problem

Fictional factory staff sorted widgets by hand, which was slow and inconsistent between shifts.

## My contributions

I wrote the camera capture loop, the colour classifier and the sorting rules. The conveyor hardware belonged to the existing fictional system.

## Architecture

A camera captures each widget, a small convolutional classifier predicts its colour class, and a rules engine sends it to one of seven bins.

## Challenges and decisions

Lighting changed through the day, so colour predictions drifted. I added white-balance calibration at the start of every shift instead of retraining the classifier.

## Results

On the fictional test set the classifier reached a made-up accuracy figure; this section exists only to be retrieved.

## Limitations and what I would do next

The classifier cannot handle widgets with two colours. Next I would add a multi-label output.
