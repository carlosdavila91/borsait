"""
Python program to scrape obligation data from the borsaitaliana.it page.
"""

import argparse
import asyncio
import datetime
import time
from pathlib import Path

import openpyxl
from playwright.async_api import async_playwright
from rich.console import Console
from rich.progress import Progress

BASE_URL = "https://www.borsaitaliana.it/"
RELATIVE_PATH = "borsa/obbligazioni/ricerca-avanzata.html#formAndResults"


async def get_page_data(page_number: int) -> list[list[str]]:
    """Loads the page and extracts the table data."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        url = f"{BASE_URL}{RELATIVE_PATH}?page={page_number}"
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


async def scrape_pages(page_range: range, output_dir: Path) -> None:
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
            data = await get_page_data(page_number)
            all_data.append(data)
            progress.update(task, advance=1)

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

    console.print(f"[bold green]Scraping completed. Data saved to {output_path}")


async def main():
    parser = argparse.ArgumentParser(
        description="Scrape data from a paginated table on a website."
    )
    parser.add_argument(
        "--pages",
        default=100,
        type=int,
        required=True,
        help="The number of pages to scrape",
    )
    parser.add_argument(
        "--output",
        default=Path("./data"),
        type=str,
        required=True,
        help="The directory to save the output file",
    )
    args = parser.parse_args()
    n_pages = args.pages
    output_dir = Path(args.output)

    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    await scrape_pages(range(1, n_pages + 1), output_dir)
    print(f"Scraping completed in {time.time() - start_time:.2f} seconds.")


if __name__ == "__main__":
    asyncio.run(main())
