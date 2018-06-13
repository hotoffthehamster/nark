# -*- coding: utf-8 -*-

# This file is part of 'nark'.
#
# 'nark' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'nark' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'nark'.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, unicode_literals

import logging
from datetime import datetime
from future.utils import python_2_unicode_compatible

from .helpers import logging as logging_helpers

from .managers.activity import BaseActivityManager
from .managers.category import BaseCategoryManager
from .managers.fact import BaseFactManager
from .managers.tag import BaseTagManager


__all__ = ['BaseStore', ]


@python_2_unicode_compatible
class BaseStore(object):
    """
    A controller store defines the interface to interact with stored entities,
    regardless of the backend being used.

    ``self.logger`` provides a dedicated logger instance for any storage
    related logging. If you want to make use of it, just setup and attach your
    handlers and you are ready to go. Be advised though, ``self.logger`` will
    be very verbose as on ``debug`` it will log any method call and often even
    their returned instances.
    """

    def __init__(self, config):
        self.config = config
        self.init_logger()
        self.categories = BaseCategoryManager(self)
        self.activities = BaseActivityManager(self)
        self.tags = BaseTagManager(self)
        self.facts = BaseFactManager(self)
        self._now = None

    def cleanup(self):
        """
        Any backend specific teardown code that needs to be executed before
        we shut down gracefully.
        """
        raise NotImplementedError

    def init_logger(self):
        self.logger = logging.getLogger('nark.storage')
        self.logger.addHandler(logging.NullHandler())

        sql_log_level = self.config['sql_log_level']
        log_level, warn_name = logging_helpers.resolve_log_level(sql_log_level)

        try:
            self.logger.setLevel(int(log_level))
        except ValueError:
            warn_name = True
            self.logger.setLevel(logging.WARNING)

        stream_handler = logging.StreamHandler()
        formatter = logging_helpers.formatter_basic()
        formatter = logging_helpers.setupHandler(
            stream_handler, formatter, self.logger,
        )

        if warn_name:
            self.logger.warning(
                _('Unknown Backend.sql_log_level specified: {}')
                .format(sql_log_level)
            )

    @property
    def now(self):
        # Use the same 'now' for all items that need it. 'Now' is considered
        # the run of the whole command, and not different points within it.
        # (lb): It probably doesn't matter either way what we do, but I'd
        # like all facts that use now to reflect the same moment in time,
        # rather than being microseconds apart from one another.
        # (lb): Also, we use @property to convey to the caller that this
        # is not a function; i.e., the value is static, not re-calculated.
        if self._now is None:
            self._now = self._now_tz_aware()
        return self._now

    def _now_tz_aware(self):
        if self.config['tz_aware']:
            # FIXME/2018-05-23: (lb): Tests use utcnow(). Should they honor tz_aware?
            return datetime.utcnow()
        else:
            return datetime.now()
