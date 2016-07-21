# Copyright 2016 ZEROFAIL
#
# This file is part of Goblin.
#
# Goblin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Goblin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Goblin.  If not, see <http://www.gnu.org/licenses/>.

"""Helper functions and class to map between OGM Elements <-> DB Elements"""

import logging
import functools

from goblin import exception

logger = logging.getLogger(__name__)


#######IMPLEMENT
def map_props_to_db(element, mapping):
    """Convert OGM property names/values to DB property names/values"""
    property_tuples = []
    props = mapping.ogm_properties
    for ogm_name, (db_name, data_type) in props.items():
        val = getattr(element, ogm_name, None)
        if val and isinstance(val, (list, set)):
            card = None
            for v in val:
                # get metaprops as dic
                metaprops = {}
                property_tuples.append(
                    (card, db_name, data_type.to_db(v.value), metaprops))
                card = v.cardinality
        else:
            if hasattr(val, '__mapping__'):
                val = val.value
            property_tuples.append((None, db_name, data_type.to_db(val), None))
    return property_tuples


def map_vertex_to_ogm(result, element, *, mapping=None):
    """Map a vertex returned by DB to OGM vertex"""
    for db_name, value in result['properties'].items():
        if len(value) > 1:
            # parse and assign vertex props + metas
            value = [v['value'] for v in value]
        else:
            value = value[0]['value']
        name, data_type = mapping.db_properties.get(db_name, (db_name, None))
        if data_type:
            value = data_type.to_ogm(value)
        setattr(element, name, value)
    setattr(element, '__label__', result['label'])
    setattr(element, 'id', result['id'])
    return element


def map_edge_to_ogm(result, element, *, mapping=None):
    """Map an edge returned by DB to OGM edge"""
    for db_name, value in result.get('properties', {}).items():
        name, data_type = mapping.db_properties.get(db_name, (db_name, None))
        if data_type:
            value = data_type.to_ogm(value)
        setattr(element, name, value)
    setattr(element, '__label__', result['label'])
    setattr(element, 'id', result['id'])
    setattr(element.source, '__label__', result['outVLabel'])
    setattr(element.target, '__label__', result['inVLabel'])
    sid = result['outV']
    esid = getattr(element.source, 'id', None)
    if _check_id(sid, esid):
        from goblin.element import GenericVertex
        element.source = GenericVertex()
    tid = result['inV']
    etid = getattr(element.target, 'id', None)
    if _check_id(tid, etid):
        from goblin.element import GenericVertex
        element.target = GenericVertex()
    setattr(element.source, 'id', sid)
    setattr(element.target, 'id', tid)
    return element


def _check_id(rid, eid):
    if eid and rid != eid:
        logger.warning('Edge vertex id has changed')
        return True
    return False


# DB <-> OGM Mapping
def create_mapping(namespace, properties):
    """Constructor for :py:class:`Mapping`"""
    element_type = namespace.get('__type__', None)
    if element_type:
        if element_type == 'vertex':
            mapping_func = map_vertex_to_ogm
            return Mapping(namespace, element_type, mapping_func, properties)
        elif element_type == 'edge':
            mapping_func = map_edge_to_ogm
            return Mapping(namespace, element_type, mapping_func, properties)


class Mapping:
    """
    This class stores the information necessary to map between an OGM element
    and a DB element.
    """
    def __init__(self, namespace, element_type, mapper_func, properties):
        self._label = namespace['__label__']
        self._element_type = element_type
        self._mapper_func = functools.partial(mapper_func, mapping=self)
        self._db_properties = {}
        self._ogm_properties = {}
        self._map_properties(properties)

    @property
    def label(self):
        """Element label"""
        return self._label

    @property
    def mapper_func(self):
        """Function responsible for mapping db results to ogm"""
        return self._mapper_func

    @property
    def db_properties(self):
        """A dictionary of property mappings"""
        return self._db_properties

    @property
    def ogm_properties(self):
        """A dictionary of property mappings"""
        return self._ogm_properties

    def __getattr__(self, value):
        try:
            mapping, _ = self._ogm_properties[value]
            return mapping
        except:
            raise exception.MappingError(
                "unrecognized property {} for class: {}".format(
                    value, self._element_type))

    def _map_properties(self, properties):
        for name, prop in properties.items():
            data_type = prop.data_type
            if prop.db_name:
                db_name = prop.db_name
            else:
                db_name = '{}__{}'.format(self._label, name)
            if hasattr(prop, '__mapping__'):
                if not self._element_type == 'vertex':
                    raise exception.MappingError(
                        'Only vertices can have vertex properties')
            self._db_properties[db_name] = (name, data_type)
            self._ogm_properties[name] = (db_name, data_type)

    def __repr__(self):
        return '<{}(type={}, label={}, properties={})>'.format(
            self.__class__.__name__, self._element_type, self._label,
            self._ogm_properties)
