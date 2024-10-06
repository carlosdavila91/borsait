@echo off
set /p pages="Enter the number of pages to scrape (default: 100): "
set /p output="Enter the output directory (default: data): "

if "%pages%"=="" set pages=100
if "%output%"=="" set output=data

BorsaScraper.exe --pages %pages% --output "%output%"
pause