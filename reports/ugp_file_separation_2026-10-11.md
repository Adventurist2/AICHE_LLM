# UGP file separation

All 12,276 destination files match their original SHA256 hashes; all source paths moved; category counts and total inventory match.

Use each extraction_input folder as INPUT_DIR for file_management.ipynb. Set a separate chunk output folder per year, then point the extraction notebook to that output.

The extraction_input folders contain the original paper JSON arrays, including records with blank abstracts. No record contents were modified.

| Year | Paper JSON files | Paper records | Records with abstracts |
|---|---:|---:|---:|
| 2017 | 1083 | 6640 | 2108 |
| 2020 | 988 | 5606 | 1600 |
| 2021 | 1018 | 5776 | 1531 |
| 2022 | 995 | 5910 | 1304 |

## Input paths

- 2017: `C:\Users\chand.CHANDAN\Downloads\UGP_2017-20261006T091905Z-1-001\UGP_2017\extraction_input`
- 2020: `C:\Users\chand.CHANDAN\Downloads\UGP_2020-20261006T091738Z-1-001\UGP_2020\extraction_input`
- 2021: `C:\Users\chand.CHANDAN\Downloads\UGP_2021-20261006T091753Z-1-001\UGP_2021\extraction_input`
- 2022: `C:\Users\chand.CHANDAN\Downloads\UGP_2022-20261006T091807Z-1-001\UGP_2022\extraction_input`

## Other folders

- paper_links: links_Session*.json
- session_metadata: sessions_Session*.json
- supporting_files: checkpoints, program index, location summary, CSV and other scraper state

All filenames and contents are preserved. The JSON manifest lists every original/destination path and hash.
