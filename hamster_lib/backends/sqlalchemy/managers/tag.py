# -*- coding: utf-8 -*-

# This file is part of 'hamster-lib'.
#
# 'hamster-lib' is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'hamster-lib' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 'hamster-lib'.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from builtins import str

from future.utils import python_2_unicode_compatible
from six import text_type
from sqlalchemy import asc, desc, func
from sqlalchemy.exc import IntegrityError

from . import query_apply_limit_offset
from ..objects import AlchemyFact, AlchemyTag, fact_tags
from ....managers.tag import BaseTagManager


@python_2_unicode_compatible
class TagManager(BaseTagManager):
    def get_or_create(self, tag, raw=False):
        """
        Custom version of the default method in order to provide access to
        alchemy instances.

        Args:
            tag (hamster_lib.Tag): Tag we want.
            raw (bool): Wether to return the AlchemyTag instead.

        Returns:
            hamster_lib.Tag or None: Tag.
        """

        message = _("Received {!r} and raw={}.".format(tag, raw))
        self.store.logger.debug(message)

        try:
            tag = self.get_by_name(tag.name, raw=raw)
        except KeyError:
            tag = self._add(tag, raw=raw)
        return tag

    def _add(self, tag, raw=False):
        """
        Add a new tag to the database.

        This method should not be used by any client code. Call ``save`` to make
        the decission wether to modify an existing entry or to add a new one is
        done correctly..

        Args:
            tag (hamster_lib.Tag): Hamster Tag instance.
            raw (bool): Wether to return the AlchemyTag instead.

        Returns:
            hamster_lib.Tag: Saved instance, as_hamster()

        Raises:
            ValueError: If the name to be added is already present in the db.
            ValueError: If tag passed already got an PK. Indicating that update
                would be more apropiate.
        """

        message = _("Received {!r} and raw={}.".format(tag, raw))
        self.store.logger.debug(message)

        if tag.pk:
            message = _(
                "The tag ('{!r}') being added already has a PK."
                " Perhaps you want to ``_update`` instead?".format(tag)
            )
            self.store.logger.error(message)
            raise ValueError(message)
        alchemy_tag = AlchemyTag(
            pk=None,
            name=tag.name,
            deleted=tag.deleted,
            hidden=tag.hidden,
        )
        self.store.session.add(alchemy_tag)
        try:
            self.store.session.commit()
        except IntegrityError as e:
            message = _(
                "An error occured! Are you sure that tag.name "
                "is not already present? Error: '{}'.".format(e)
            )
            self.store.logger.error(message)
            raise ValueError(message)
        self.store.logger.debug(_("'{!r}' added.".format(alchemy_tag)))

        if not raw:
            alchemy_tag = alchemy_tag.as_hamster(self.store)
        return alchemy_tag

    def _update(self, tag):
        """
        Update a given Tag.

        Args:
            tag (hamster_lib.Tag): Tag to be updated.

        Returns:
            hamster_lib.Tag: Updated tag.

        Raises:
            ValueError: If the new name is already taken.
            ValueError: If tag passed does not have a PK.
            KeyError: If no tag with passed PK was found.
        """

        message = _("Received {!r}.".format(tag))
        self.store.logger.debug(message)

        if not tag.pk:
            message = _(
                "The tag passed ('{!r}') does not seem to havea PK. "
                "We don't know which entry to modify.".format(tag)
            )
            self.store.logger.error(message)
            raise ValueError(message)
        alchemy_tag = self.store.session.query(AlchemyTag).get(tag.pk)
        if not alchemy_tag:
            message = _("No tag with PK: {} was found!".format(tag.pk))
            self.store.logger.error(message)
            raise KeyError(message)
        alchemy_tag.name = tag.name

        try:
            self.store.session.commit()
        except IntegrityError as e:
            message = _(
                "An error occured! Are you sure that tag.name is not "
                "already present in the database? Error: '{}'.".format(e)
            )
            self.store.logger.error(message)
            raise ValueError(message)

        return alchemy_tag.as_hamster(self.store)

    def remove(self, tag):
        """
        Delete a given tag.

        Args:
            tag (hamster_lib.Tag): Tag to be removed.

        Returns:
            None: If everything went alright.

        Raises:
            KeyError: If the ``Tag`` can not be found by the backend.
            ValueError: If tag passed does not have an pk.
        """

        message = _("Received {!r}.".format(tag))
        self.store.logger.debug(message)

        if not tag.pk:
            message = _("PK-less Tag. Are you trying to remove a new Tag?")
            self.store.logger.error(message)
            raise ValueError(message)
        alchemy_tag = self.store.session.query(AlchemyTag).get(tag.pk)
        if not alchemy_tag:
            message = _("``Tag`` can not be found by the backend.")
            self.store.logger.error(message)
            raise KeyError(message)
        self.store.session.delete(alchemy_tag)
        message = _("{!r} successfully deleted.".format(tag))
        self.store.logger.debug(message)
        self.store.session.commit()

    def get(self, pk):
        """
        Return a tag based on their pk.

        Args:
            pk (int): PK of the tag to be retrieved.

        Returns:
            hamster_lib.Tag: Tag matching given PK.

        Raises:
            KeyError: If no such PK was found.

        Note:
            We need this for now, as the service just provides pks, not names.
        """

        message = _("Received PK: '{}'.".format(pk))
        self.store.logger.debug(message)

        result = self.store.session.query(AlchemyTag).get(pk)
        if not result:
            message = _("No tag with 'pk: {}' was found!".format(pk))
            self.store.logger.error(message)
            raise KeyError(message)
        message = _("Returning {!r}.".format(result))
        self.store.logger.debug(message)
        return result.as_hamster(self.store)

    def get_by_name(self, name, raw=False):
        """
        Return a tag based on its name.

        Args:
            name (str): Unique name of the tag.
            raw (bool): Wether to return the AlchemyTag instead.

        Returns:
            hamster_lib.Tag: Tag of given name.

        Raises:
            KeyError: If no tag matching the name was found.

        """

        message = _("Received name: '{}', raw={}.".format(name, raw))
        self.store.logger.debug(message)

        name = text_type(name)
        try:
            result = self.store.session.query(AlchemyTag).filter_by(name=name).one()
        except NoResultFound:
            message = _("No tag with 'name: {}' was found!".format(name))
            self.store.logger.error(message)
            raise KeyError(message)

        if not raw:
            result = result.as_hamster(self.store)
            self.store.logger.debug(_("Returning: {!r}.").format(result))
        return result

    def get_all(self, *args, sort_col='', **kwargs):
        """Get all tags."""
        if not sort_col:
            sort_col = 'name'
        return self._get_all(*args, include_usage=False, sort_col=sort_col, **kwargs)

    def get_all_by_usage(self, *args, sort_col='', **kwargs):
        if not sort_col:
            sort_col = 'usage'
        return self._get_all(*args, include_usage=True, sort_col=sort_col, **kwargs)

    def _get_all(
        self,
        include_usage=True,
        search_term='',
        sort_col='',
        sort_order='',
        **kwargs
    ):
        """
        Get all tags, with filtering and sorting options.

        Returns:
            list: List of all Tags present in the database,
                  ordered by lower(name), or most recently
                  used; possibly filtered by a search term.
        """

        query, count_col = self._get_all_query(include_usage)

        # FIXME/MIGATIONS: (lb): Add column: Fact.deleted.
        #condition = and_(condition, not AlchemyFact.deleted)
        #query = query.filter(condition)

        query = self._get_all_group_by(query, include_usage)

        query = self._get_all_order_by(query, sort_col, sort_order, include_usage, count_col)

        query = query_apply_limit_offset(query, **kwargs)

        query = self._get_all_with_entities(query, count_col)

        self.store.logger.debug(_('query: {}'.format(str(query))))

        results = query.all()

        return results

    def _get_all_query(self, include_usage):
        if not include_usage:
            count_col = None
            query = self.store.session.query(AlchemyTag)
        else:
            count_col = func.count(AlchemyTag.pk).label('uses')
            query = self.store.session.query(AlchemyTag, count_col)
            query = query.join(fact_tags)
            query = query.join(AlchemyFact)
        return query, count_col


    def _get_all_group_by(self, query, include_usage):
        if not include_usage:
            return query
        query = query.group_by(AlchemyTag.pk)
        return query

    def _get_all_order_by(self, query, sort_col, sort_order, include_usage, count_col):
        direction = desc if sort_order == 'desc' else asc
        if sort_col == 'start':
            assert include_usage
            direction = desc if not sort_order else direction
            query = query.order_by(direction(AlchemyFact.start))
        elif sort_col == 'usage':
            assert include_usage and count_col is not None
            direction = desc if not sort_order else direction
            query = query.order_by(direction(count_col))
        else:
            # Meh. Rather than make a custom --order for each command,
            # just using the same big list. So 'activity', 'category',
            # etc., are acceptable here, if not simply ignored.
            assert sort_col in ('', 'name', 'activity', 'category', 'tag', 'fact')
            query = query.order_by(direction(AlchemyTag.name))
        return query

    def _get_all_with_entities(self, query, count_col):
        if count_col is None:
            return query
        query = query.with_entities(AlchemyTag, count_col)
        return query
