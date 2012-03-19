from pylons import config

import logging

import colander

from pylons import app_globals, request, response, tmpl_context as c
from pylons.controllers.util import redirect, abort
from pylons.i18n import _

from openspending.model import meta as db, View
from openspending.ui.lib import helpers as h, widgets
from openspending.lib import json
from openspending.ui.lib.views import handle_request
from openspending.ui.lib.base import BaseController, render, require
from openspending.lib.jsonexport import to_jsonp

log = logging.getLogger(__name__)


class JSONSchemaType(colander.SchemaType):
    def serialize(self, node, appstruct):
        return json.dumps(appstruct)

    def deserialize(self, node, cstruct):
        try:
            return json.loads(cstruct)
        except Exception as exc:
            raise colander.Invalid(node, unicode(exc))


def valid_widget_name(widget):
    if widget in widgets.list_widgets():
        return True
    return _("Invalid widget type: %r") % widget


class CreateView(colander.MappingSchema):
    label = colander.SchemaNode(colander.String())
    widget = colander.SchemaNode(colander.String(),
        validator=colander.Function(valid_widget_name))
    description = colander.SchemaNode(colander.String(),
        missing=None)
    state = colander.SchemaNode(JSONSchemaType())


def make_name(dataset, label):
    from openspending.lib.util import slugify
    from itertools import count
    name = name_orig = slugify(label)
    view = View.by_name(dataset, name)
    for i in count():
        if view is None:
            return name
        name = name_orig + str(i)
        view = View.by_name(dataset, name)


class ViewController(BaseController):

    def _get_view(self, dataset, name):
        self._get_dataset(dataset)
        c.view = View.by_name(c.dataset, name)
        if c.view is None:
            abort(404, _('Sorry, there is no view %r') % name)
        require.view.read(c.dataset, c.view)

    def index(self, dataset, format='html'):
        self._get_dataset(dataset)
        handle_request(request, c, c.dataset)
        c.views = View.all_by_dataset(c.dataset)
        if format == 'json':
            return to_jsonp([v.as_dict() for v in c.views])
        else:
            return render('view/index.html')

    def new(self, dataset, errors={}):
        self._get_dataset(dataset)
        handle_request(request, c, c.dataset)
        c.widgets = dict([(n, widgets.get_widget(n)) \
            for n in widgets.list_widgets()])
        c.errors = errors
        return render('view/new.html')

    def create(self, dataset):
        self._get_dataset(dataset)
        require.view.create(c.dataset)
        handle_request(request, c, c.dataset)
        try:
            data = CreateView().deserialize(request.params)
            view = View(c.dataset, c.account, data['widget'],
                        data['state'])
            view.name = make_name(c.dataset, data['label'])
            view.label = data['label']
            view.description = data['description']
            view.public = True
            db.session.add(view)
            db.session.commit()
            redirect(h.url_for(controller='view', action='view',
                dataset=c.dataset.name, name=view.name))
        except colander.Invalid as inv:
            return self.new(dataset, errors=inv.asdict())

    def view(self, dataset, name, format='html'):
        self._get_view(dataset, name)
        print format
        if format == 'json':
            return to_jsonp(c.view.as_dict())
        else:
            return render('view/view.html')

    def embed(self, dataset):
        self._get_dataset(dataset)
        c.widget = request.params.get('widget')
        if c.widget is None:
            abort(400, _("No widget type has been specified."))
        try:
            c.widget = widgets.get_widget(c.widget)
            c.state = json.loads(request.params.get('state', '{}'))
        except ValueError as ve:
            abort(400, unicode(ve))
        return render('view/embed.html')
