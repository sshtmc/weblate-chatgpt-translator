import json
import logging
import os
import re
import time
from typing import List, Optional, Tuple

import polib
from openai import OpenAI
from polib import POEntry, POFile

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self):
        self.openai = OpenAI(
            api_key=os.environ.get('OPENAI_KEY'),
            timeout=60 * 5,
        )

    def tanslate_po_file(self, contents: str, language_code: str) -> Tuple[POFile, int]:
        po = polib.pofile(contents)

        messages_to_translate = []
        untranslated_messages = po.untranslated_entries()
        for message in po:
            if message in untranslated_messages or message.msgstr == '' or message.fuzzy:
                messages_to_translate.append(message)

        if not messages_to_translate:
            return po, 0

        self.__translate(messages_to_translate, language_code)

        return po, len(messages_to_translate)

    def __translate(
            self,
            messages: List[POEntry],
            language: str,
            max_messages_per_request: int = 100,
            total_count: Optional[int] = None,
            translated_count: Optional[int] = 0,
            recursion_depth: int = 0):

        recursion_depth += 1

        if recursion_depth > 1000:
            raise Exception("Recursion depth exceeded")

        if total_count is None:
            total_count = len(messages)

        if not messages or max_messages_per_request < 1:
            return

        batches = []
        if len(messages) > max_messages_per_request:
            split_index = len(messages) // 2
            batches.append(messages[:split_index])
            batches.append(messages[split_index:])

            for batch in batches:
                try:
                    self.__translate(
                        batch,
                        language,
                        max_messages_per_request=max_messages_per_request,
                        total_count=total_count,
                        translated_count=translated_count,
                        recursion_depth=recursion_depth)
                except Exception:
                    logger.exception("Failed to translate batch. Taking a break before retrying with smaller batch")
                    time.sleep(60)
                    self.__translate(
                        batch,
                        language,
                        max_messages_per_request=max_messages_per_request // 2,
                        total_count=total_count,
                        translated_count=translated_count,
                        recursion_depth=recursion_depth)

                translated_count += len(batch)
        else:
            self.__translate_batch(messages, language)
            translated_count += len(messages)
            logger.info("Translated %d out of %d messages", translated_count, total_count)

    def __translate_batch(self, batch: List[POEntry], language: str):
        input_json = []
        for i, entry in enumerate(batch):
            input_data = {"id": i}

            if entry.msgid_plural:
                input_data.update({"text": entry.msgid, "text_plural": entry.msgid_plural})
            else:
                input_data["text"] = entry.msgid

            input_json.append(input_data)
        input_json_text = json.dumps(input_json)

        client = self.openai
        prompt = f"""
        I have a list of messages in english.
        I need to translate them to {language}.

        Reply with the same json list, but with the translated messages.

        {input_json_text}
        """

        logger.info("Sending translation request to openai for %d messages", len(batch))
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="gpt-4",
            stop=[
                "\n\n\n",
            ]
        )

        reply = chat_completion.choices[0].message.content
        logger.info("Got reply from openai")

        pattern = r'\[.+\]'
        matches = re.findall(pattern, reply, re.DOTALL)
        if not matches:
            parse_error_message = f"Could not parse openai reply: {reply}"
            logger.error(parse_error_message)
            raise Exception(parse_error_message)

        reply = matches[0]

        try:
            reply = json.loads(reply)
        except json.JSONDecodeError as e:
            parse_error_message = f"Could not load json from openai reply: {reply}"
            logger.exception(parse_error_message)
            raise

        if len(reply) != len(batch):
            parse_error_message = f"Openai reply has different length than batch: {reply}"
            logger.error(parse_error_message)
            raise Exception(parse_error_message)

        for i, (translation_reply, translation) in enumerate(zip(reply, batch)):
            if 'id' not in translation_reply:
                parse_error_message = f"Openai reply is missing id: {reply}"
                logger.error(parse_error_message)
                raise Exception(parse_error_message)

            reply_index = translation_reply['id']
            if reply_index != i:
                parse_error_message = f"Openai reply has different order than batch: {reply}"
                logger.error(parse_error_message)
                raise Exception(parse_error_message)

            if not translation.msgid_plural:
                if 'text' not in translation_reply:
                    parse_error_message = f"Openai reply is missing text: {reply}"
                    logger.error(parse_error_message)
                    raise Exception(parse_error_message)

                translation.msgstr = translation_reply['text']
            else:
                if 'text' not in translation_reply or 'text_plural' not in translation_reply:
                    parse_error_message = f"Openai reply is missing text or text_plural: {reply}"
                    logger.error(parse_error_message)
                    raise Exception(parse_error_message)

                translation.msgstr_plural = {
                    '0': translation_reply['text'],
                    '1': translation_reply['text_plural']
                }

            translation.fuzzy = False

        logger.info("Batch translated successfully")
