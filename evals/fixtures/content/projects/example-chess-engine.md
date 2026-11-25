---
id: example-chess-engine
title: Example Chess Engine
status: approved
version: 1
updated: 2026-03-10
type: personal
permission: "fixture, not real"
summary: A fictional chess engine. Used only for evaluation tests.
skills: [search algorithms]
languages: [Rust]
---

## Overview

The Example Chess Engine is a fictional program that plays chess using alpha-beta search.

## Implementation details

Move generation uses bitboards. The search uses alpha-beta pruning with iterative deepening and a transposition table keyed by Zobrist hashes.

## Challenges and decisions

The transposition table caused subtle bugs when hash collisions occurred, so I added a verification key to every entry.

## Limitations and what I would do next

The evaluation function is hand-written. Next I would try a small learned evaluation network.
