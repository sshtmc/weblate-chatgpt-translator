import argparse
import json
import logging
import logging.config
import os
import threading
import time
from typing import Optional, Tuple

import wlc
from polib import POFile
from wlc import Translation

from log_config import LOGGING_CONFIG
from translator import Translator

# Apply the logging configuration
logging.config.dictConfig(LOGGING_CONFIG)

logger = logging.getLogger(__name__)


def get_weblate_wrapper():
    return wlc.Weblate(
        key=os.environ.get('WEBLATE_API_KEY'),
        url=os.environ.get('WEBLATE_API_URL')
    )


def parse_arguments():
    # Create the parser
    parser = argparse.ArgumentParser(description='Translate Weblate translations using OpenAI')

    # Add arguments
    parser.add_argument('--project', type=str, help='Project slug', required=True)
    parser.add_argument('--components', type=str, help='Component slug', nargs='+', default=None, required=False)
    parser.add_argument('--languages', type=str, help='Language code', nargs='+', default=None, required=False)

    # Parse the command line arguments
    return parser.parse_args()


def download_translation(translation_url: str) -> Tuple[Optional[Translation], Optional[str]]:
    # Returns po file contents as string
    ATTEMPTS = 3
    PAUSE_SECONDS = 60

    for i in range(0, ATTEMPTS):
        try:
            logger.info(f'Downloading translation file for {translation_url}')
            weblate = get_weblate_wrapper()
            translation = Translation(weblate, translation_url)
            file = translation.download(convert='po')
            file_contents = file.decode('utf-8')
            logger.info(f'Translation file downloaded for {translation_url}')
            return translation, file_contents
        except Exception:
            logger.exception(f"Failed to download translation file for {translation_url}")
            if i < ATTEMPTS - 1:
                logger.error(f'Pausing for {PAUSE_SECONDS} seconds before retrying')
                time.sleep(PAUSE_SECONDS)
                continue

            return None, None


def upload_translation(
        translation_url: str,
        translated_po: POFile):
    ATTEMPTS = 5
    PAUSE_SECONDS = 120

    for i in range(0, ATTEMPTS):
        try:
            logger.info(f'Uploading translation file for {translation_url}')

            weblate = get_weblate_wrapper()
            translation = Translation(weblate, translation_url)
            file_type = translation['filename'].split('.')[-1]

            if file_type == 'po':
                contents = translated_po.__unicode__()
            elif file_type == 'arb':
                contents = json.dumps({msg.msgctxt: msg.msgstr for msg in translated_po if msg.msgstr != ''})
            else:
                raise Exception(f"Unsupported file type {file_type}")

            upload_result = translation.upload(
                file=contents,
                overwrite=False,
                method='translate')

            logger.info(f'Committing translation file for {translation_url}')
            translation.commit()

            logger.info(f'Pushing translation file for {translation_url}')
            translation.push()

            logger.info(f'Translations uploaded for {translation_url}')
            return upload_result
        except Exception:
            logger.exception(f"Failed to upload translation file for {translation_url}")
            if i < ATTEMPTS - 1:
                logger.error(f'Pausing for {PAUSE_SECONDS} seconds before retrying')
                time.sleep(PAUSE_SECONDS)
                continue

            return None


def perform_translations(po_file_contents: str, language_code: str) -> Tuple[Optional[POFile], int]:
    ATTEMPTS = 3
    PAUSE_SECONDS = 120

    for i in range(0, ATTEMPTS):
        try:
            logger.info(f'Performing translations')
            translator = Translator()
            translated_po, translated_count = translator.tanslate_po_file(po_file_contents, language_code)
            return translated_po, translated_count
        except Exception:
            logger.exception(f"Translations failed")
            if i < ATTEMPTS - 1:
                logger.error(f'Pausing for {PAUSE_SECONDS} seconds before retrying')
                time.sleep(PAUSE_SECONDS)
                continue

            return None, 0


def translate(tranlation_url: str):
    logger.info(f'Starting trasnaltion thread for {tranlation_url}')

    translation, file_contents = download_translation(tranlation_url)
    if not translation or not file_contents:
        logger.error(f'Failed to download translation file for {tranlation_url}. Aborting translation.')
        return

    language_code = translation['language_code']
    language_name = translation['language']['name']
    translated_po, trasnalted_count = perform_translations(file_contents, f'{language_code}-{language_name}')

    if not translated_po:
        logger.error(f'Failed to translate file for {tranlation_url}. Aborting translation.')
        return

    if trasnalted_count == 0:
        logger.info(f'No new translations found for {tranlation_url} - done.')
        return

    logger.info(f'Found {trasnalted_count} new translations for {tranlation_url}')

    upload_result = upload_translation(tranlation_url, translated_po)

    if not upload_result:
        logger.error(f'Failed to upload translation file for {tranlation_url}')
        return

    logger.info(f'Translation finished successfully for {tranlation_url}')


def main():
    # Parse the arguments
    args = parse_arguments()
    args.project = args.project.lower()
    args.components = [c.lower() for c in args.components] if args.components else None
    args.languages = [l.lower() for l in args.languages] if args.languages else None

    logger.info(
        f"Starting translations for project {args.project} with component filters {args.components} and languages filters {args.languages}")

    weblate = get_weblate_wrapper()
    translation_threads = []
    for translation in weblate.list_translations():
        component = translation['component']
        component_id = component['slug'].lower()
        project = component['project']
        project_id = project['slug'].lower()
        language_code = translation['language_code'].lower()

        if project_id != args.project:
            continue

        if args.components and component_id not in args.components or component_id == 'glossary':
            continue

        if args.languages and language_code not in args.languages:
            continue

        logger.info(f'Creating translation thread for {project_id} {component_id} {language_code}')
        translation_threads.append(
            threading.Thread(
                target=translate,
                name=f"TranslationThread {project_id} {component_id} {language_code}",
                kwargs={
                    'tranlation_url': translation['url']
                }
            ))

    logger.info("Starting translation threads")

    batch = 3
    while len(translation_threads) > 0:
        batch_threads = translation_threads[:batch]
        translation_threads = translation_threads[batch:]

        for thread in batch_threads:
            thread.start()

        for thread in batch_threads:
            thread.join()

    logger.info("All translations finished")


if __name__ == "__main__":
    main()
