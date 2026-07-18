#!/bin/sh

black "$1" & pylint "$1"
