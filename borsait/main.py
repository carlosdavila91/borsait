"""
Python program to scrape obligation data from the borsaitaliana.it page.
"""

import argparse
import asyncio
import datetime
import sys
import time
from pathlib import Path

import openpyxl
from playwright.async_api import async_playwright
from rich.console import Console
from rich.progress import Progress

BASE_URL = "https://www.borsaitaliana.it/"
RELATIVE_PATH = "borsa/obbligazioni/ricerca-avanzata.html#formAndResults"
SCRAPE_URL = f"{BASE_URL}{RELATIVE_PATH}"


async def get_page_data(page_number: int, headless: bool) -> list[list[str]]:
    """Loads the page and extracts the table data."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()

        url = f"{SCRAPE_URL}?page={page_number}"
        await page.goto(url)

        # Wait for the table to be rendered
        await page.wait_for_selector("table")

        # Extract the table data
        table = await page.query_selector_all("table")
        table_element = table[0]
        column_names = [
            await cell.inner_text()
            for cell in await table_element.query_selector_all("th")
        ]
        rows = await table_element.query_selector_all("tr")
        data = [
            [await cell.inner_text() for cell in await row.query_selector_all("td")]
            for row in rows[1:]
        ]

        await browser.close()
        return [column_names] + data


async def save_data(all_data: list[list[str]], output_path: Path) -> None:
    """Saves the scraped data to an excel workbook."""
    # Flatten the list of data and write to an Excel file
    data = [row for page_data in all_data for row in page_data]

    # Prepare the excel file
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    column_names = data[0]
    sheet.append(column_names)  # type: ignore
    for row in data[1:]:
        if row != column_names and row != []:
            sheet.append(row)  # type: ignore
    workbook.save(output_path)


async def run_scrape(page_range: range, output_dir: Path, headless: bool) -> None:
    """
    Runs the whole process: scrapes all the data and adds it to the output file.
    """
    today = datetime.date.today()
    file_name = f"{today}_borsa-italiana.xlsx"
    output_path = output_dir / file_name

    console = Console()
    with Progress(console=console, transient=True) as progress:
        task = progress.add_task("[green]Scraping pages...", total=len(page_range))

        all_data = []
        for page_number in page_range:
            data = await get_page_data(page_number, headless=headless)
            all_data.append(data)
            progress.update(task, advance=1)

    await save_data(all_data=all_data, output_path=output_path)

    console.print(f"[bold green]Scraping completed. Data saved to {output_path}")


async def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Estrae dati da la tabella paginata sul sito web {SCRAPE_URL}.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--pages",
        "-p",
        default=100,
        type=int,
        required=False,
        help="Il numero di pagine da estrarre",
    )
    parser.add_argument(
        "--output",
        "-d",
        type=str,
        required=True,
        help="La directory dove salvare il file di output",
    )
    parser.add_argument(
        "--watching",
        action="store_true",
        default=False,
        help="Se eseguire il browser in modalità senza intestazione.",
    )
    return parser


async def async_main():
    parser = await get_parser()

    # If no arguments are provided, print help and exit
    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()
    pages = args.pages
    output_dir = Path(args.output)
    headless = not args.watching

    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    await run_scrape(range(1, pages + 1), output_dir, headless)
    print(f"Scraping completed in {time.time() - start_time:.2f} seconds.")


def main():
    """Synchronous wrapper to the main function."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
