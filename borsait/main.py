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


async def get_page_data(
    page_number: int, headless: bool, verbose: bool
) -> list[list[str]]:
    """Loads the page and extracts the table data."""
    console = Console()
    try:
        async with async_playwright() as p:
            if verbose:
                console.print(f"[yellow]Launching browser (headless={headless})")
            browser = await p.firefox.launch(headless=headless)
            page = await browser.new_page()

            url = f"{SCRAPE_URL}?page={page_number}"
            if verbose:
                console.print(f"[yellow]Navigating to page {page_number}: {url}")

            await page.goto(url, timeout=30000)  # 30 seconds timeout
            if verbose:
                console.print(f"[green]Page {page_number} loaded successfully")

            # Wait for the table to be rendered
            if verbose:
                console.print("[yellow]Waiting for table to load...")
            await page.wait_for_selector("table", timeout=30000)
            if verbose:
                console.print("[green]Table found")

            # Extract the table data
            table = await page.query_selector_all("table")
            if not table:
                raise ValueError("No table found on page")

            table_element = table[0]
            if verbose:
                console.print("[yellow]Extracting column names...")
            column_names = [
                await cell.inner_text()
                for cell in await table_element.query_selector_all("th")
            ]

            if verbose:
                console.print("[yellow]Extracting row data...")
            rows = await table_element.query_selector_all("tr")
            data = [
                [await cell.inner_text() for cell in await row.query_selector_all("td")]
                for row in rows[1:]
            ]

            if verbose:
                console.print(
                    f"[green]Successfully extracted {len(data)} rows from page {page_number}"
                )

            await browser.close()
            return [column_names] + data

    except Exception as e:
        error_msg = f"Error on page {page_number}: {str(e)}"
        if verbose:
            console.print(f"[red]{error_msg}")
        raise Exception(error_msg)


async def save_data(
    all_data: list[list[str]], output_path: Path, verbose: bool
) -> None:
    """Saves the scraped data to an excel workbook."""
    console = Console()
    if verbose:
        console.print("[yellow]Preparing to save data to Excel...")

    # Flatten the list of data and write to an Excel file
    data = [row for page_data in all_data for row in page_data]

    if verbose:
        console.print(f"[yellow]Creating Excel workbook at {output_path}")

    # Prepare the excel file
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    column_names = data[0]
    sheet.append(column_names)  # type: ignore

    if verbose:
        console.print(f"[yellow]Writing {len(data)-1} rows to Excel...")

    for row in data[1:]:
        if row != column_names and row != []:
            sheet.append(row)  # type: ignore

    workbook.save(output_path)
    if verbose:
        console.print("[green]Excel file saved successfully")


async def run_scrape(
    page_range: range, output_dir: Path, headless: bool, verbose: bool
) -> None:
    """
    Runs the whole process: scrapes all the data and adds it to the output file.
    """
    today = datetime.date.today()
    file_name = f"{today}_borsa-italiana.xlsx"
    output_path = output_dir / file_name
    console = Console()

    if verbose:
        console.print(f"[yellow]Starting scraping process for {len(page_range)} pages")

    with Progress(console=console, transient=not verbose) as progress:
        task = progress.add_task("[green]Scraping pages...", total=len(page_range))
        all_data = []
        for page_number in page_range:
            try:
                data = await get_page_data(
                    page_number, headless=headless, verbose=verbose
                )
                all_data.append(data)
                progress.update(task, advance=1)
            except Exception as e:
                console.print(f"[red]Failed to scrape page {page_number}: {str(e)}")
                if not verbose:
                    continue
                if (
                    console.input("[yellow]Do you want to continue? (y/n): ").lower()
                    != "y"
                ):
                    break

    await save_data(all_data=all_data, output_path=output_path, verbose=verbose)
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
        "--no-headless",
        action="store_true",
        default=False,
        help="Disabilita la modalità headless (mostra il browser)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Abilita la modalità verbose per il debug",
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
    headless = not args.no_headless
    verbose = args.verbose

    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    console = Console()
    if verbose:
        console.print("[yellow]Starting scraping process with settings:")
        console.print(f"[yellow]Pages: {pages}")
        console.print(f"[yellow]Output directory: {output_dir}")
        console.print(f"[yellow]Headless mode: {headless}")

    start_time = time.time()
    await run_scrape(range(1, pages + 1), output_dir, headless, verbose)
    elapsed_time = time.time() - start_time
    console.print(f"[bold green]Scraping completed in {elapsed_time:.2f} seconds.")


def main():
    """Synchronous wrapper to the main function."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
