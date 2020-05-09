# python3
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging


class SubtleFormatter(logging.Formatter):
  """Formats log records with a more subtle format for select levels.

  Shows the name of the following levels in red: ERROR, CRITICAL and FATAL.
  """

  def __init__(self, fmt, subtle_format, subtle_levels=None,
               datefmt=None, style='%'):
    """Initializes formatter for regular and subtle records.

    Args:
      fmt: Regular format.
      subtle_format: Subtle format.
      subtle_levels: List of levels to format with subtle formatter. Defaults to
        INFO if none explicitly specified.
      datefmt: Date format.
      style: Variable expansion style.
    """
    super(SubtleFormatter, self).__init__(fmt, datefmt, style)
    self.__subtle_formatter = logging.Formatter(fmt=subtle_format)
    self.subtle_levels = subtle_levels or [logging.INFO]

  def format(self, record):
    """Returns record formatted either as regular or subtle depending on level.

    Args:
      record: Logging record.
    """
    if record.levelno in self.subtle_levels:
      return self.__subtle_formatter.format(record)

    if record.levelno in [logging.ERROR, logging.CRITICAL, logging.FATAL]:
      red = '\033[1;31m'
      reset = '\033[0m'
      record.levelname = '{red}{levelname}{reset}'.format(
          red=red,
          levelname=record.levelname,
          reset=reset,
          )

    return super(SubtleFormatter, self).format(record)


handler = logging.StreamHandler()
formatter = SubtleFormatter(fmt='%(levelname)s: (%(name)s) %(message)s',
                            subtle_format='%(message)s')
handler.setFormatter(formatter)
logging.basicConfig(handlers=[handler], level=logging.INFO)
