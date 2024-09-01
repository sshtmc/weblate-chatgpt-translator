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
            logger.info('Attempting to download translation file for %s (Attempt %d/%d)', translation_url, i+1, ATTEMPTS)
            weblate = get_weblate_wrapper()
            translation = Translation(weblate, translation_url)
            file = translation.download(convert='po')
            file_contents = file.decode('utf-8')
            logger.info('Successfully downloaded translation file for %s', translation_url)
            return translation, file_contents
        except Exception as e:
            logger.exception("Failed to download translation file for %s: %s", translation_url, str(e))
            if i < ATTEMPTS - 1:
                logger.warning('Pausing for %d seconds before retry %d/%d', PAUSE_SECONDS, i+2, ATTEMPTS)
                time.sleep(PAUSE_SECONDS)
                continue

            logger.error('All attempts to download translation file for %s have failed', translation_url)
            return None, None


def upload_translation(
        translation_url: str,
        translated_po: POFile):
    ATTEMPTS = 5
    PAUSE_SECONDS = 120

    for i in range(0, ATTEMPTS):
        try:
            logger.info('Attempting to upload translation file for %s (Attempt %d/%d)', translation_url, i+1, ATTEMPTS)

            weblate = get_weblate_wrapper()
            translation = Translation(weblate, translation_url)
            file_type = translation['filename'].split('.')[-1]

            if file_type == 'po':
                contents = translated_po.__unicode__()
            elif file_type == 'arb':
                contents = json.dumps({msg.msgctxt: msg.msgstr for msg in translated_po if msg.msgstr != ''})
            else:
                logger.error("Unsupported file type %s", file_type)
                raise ValueError(f"Unsupported file type {file_type}")

            upload_result = translation.upload(
                file=contents,
                overwrite=False,
                method='translate')

            logger.info('Committing translation file for %s', translation_url)
            translation.commit()

            logger.info('Pushing translation file for %s', translation_url)
            translation.push()

            logger.info('Successfully uploaded translations for %s', translation_url)
            return upload_result
        except Exception as e:
            logger.exception("Failed to upload translation file for %s: %s", translation_url, str(e))
            if i < ATTEMPTS - 1:
                logger.warning('Pausing for %d seconds before retry %d/%d', PAUSE_SECONDS, i+2, ATTEMPTS)
                time.sleep(PAUSE_SECONDS)
                continue

            logger.error('All attempts to upload translation file for %s have failed', translation_url)
            return None


def perform_translations(po_file_contents: str, language_code: str) -> Tuple[Optional[POFile], int]:
    ATTEMPTS = 3
    PAUSE_SECONDS = 120

    for i in range(0, ATTEMPTS):
        try:
            logger.info('Attempting to perform translations for %s (Attempt %d/%d)', language_code, i+1, ATTEMPTS)
            translator = Translator()
            translated_po, translated_count = translator.tanslate_po_file(po_file_contents, language_code)
            logger.info('Successfully performed %d translations for %s', translated_count, language_code)
            return translated_po, translated_count
        except Exception as e:
            logger.exception("Translation failed for %s: %s", language_code, str(e))
            if i < ATTEMPTS - 1:
                logger.warning('Pausing for %d seconds before retry %d/%d', PAUSE_SECONDS, i+2, ATTEMPTS)
                time.sleep(PAUSE_SECONDS)
                continue

            logger.error('All attempts to perform translations for %s have failed', language_code)
            return None, 0


def translate(translation_url: str):
    logger.info('Starting translation process for %s', translation_url)

    translation, file_contents = download_translation(translation_url)
    if not translation or not file_contents:
        logger.error('Failed to download translation file for %s. Aborting translation.', translation_url)
        return

    language_code = translation['language_code']
    language_name = translation['language']['name']
    logger.info('Translating for language: %s-%s', language_code, language_name)
    translated_po, translated_count = perform_translations(file_contents, f'{language_code}-{language_name}')

    if not translated_po:
        logger.error('Failed to translate file for %s. Aborting translation.', translation_url)
        return

    if translated_count == 0:
        logger.info('No new translations found for %s - translation process complete.', translation_url)
        return

    logger.info('Found %d new translations for %s', translated_count, translation_url)

    upload_result = upload_translation(translation_url, translated_po)

    if not upload_result:
        logger.error('Failed to upload translation file for %s', translation_url)
        return

    logger.info('Translation process finished successfully', extra={
        'translation_url': translation_url,
        'status': 'success',
        'action': 'translate',
        'translated_count': translated_count
    })

def main():
    # Parse the arguments
    args = parse_arguments()
    args.project = args.project.lower()
    args.components = [c.lower() for c in args.components] if args.components else None
    args.languages = [lang.lower() for lang in args.languages] if args.languages else None

    logger.info(
        "Starting translation process for project '%s'%s%s",
        args.project,
        f" with component filters {args.components}" if args.components else "",
        f" and language filters {args.languages}" if args.languages else ""
    )
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

        logger.info('Creating translation thread for project: %s, component: %s, language: %s', project_id, component_id, language_code)
        translation_threads.append(
            threading.Thread(
                target=translate,
                name=f"TranslationThread {project_id} {component_id} {language_code}",
                kwargs={
                    'translation_url': translation['url']
                }
            ))

    logger.info("Starting %d translation threads", len(translation_threads))

    batch = 3
    while translation_threads:
        batch_threads = translation_threads[:batch]
        translation_threads = translation_threads[batch:]

        for thread in batch_threads:
            thread.start()
            logger.debug("Started thread: %s", thread.name)

        for thread in batch_threads:
            thread.join()
            logger.debug("Completed thread: %s", thread.name)

    logger.info("All translation processes have finished")


if __name__ == "__main__":
    main()
