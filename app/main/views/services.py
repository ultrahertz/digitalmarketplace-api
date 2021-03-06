from datetime import datetime

from flask import jsonify, abort, request, current_app

from .. import main
from ... import db
from ...models import ArchivedService, Service, Supplier, Framework

from sqlalchemy import asc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.expression import false
from ...validation import detect_framework_or_400, is_valid_service_id_or_400
from ...utils import url_for, pagination_links, \
    drop_foreign_fields, display_list
from ...service_utils import validate_and_return_service_request, \
    update_and_validate_service, index_service, \
    delete_service_from_index, validate_and_return_updater_request
from sqlalchemy.types import String


@main.route('/')
def index():
    """Entry point for the API, show the resources that are available."""
    return jsonify(links={
        "services.list": url_for('.list_services', _external=True),
        "suppliers.list": url_for('.list_suppliers', _external=True)
    }
    ), 200


@main.route('/services', methods=['GET'])
def list_services():
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        abort(400, "Invalid page argument")

    supplier_id = request.args.get('supplier_id')

    services = Service.query.filter(
        Service.framework.has(Framework.expired == false())
    ).order_by(
        asc(Service.framework_id),
        asc(Service.data['lot'].cast(String).label('data_lot')),
        asc(Service.data['serviceName'].cast(String).label('data_servicename'))
    )

    if request.args.get('status'):
        services = Service.query.filter(
            Service.status.in_(request.values.getlist('status'))
        )

    if supplier_id is not None:
        try:
            supplier_id = int(supplier_id)
        except ValueError:
            abort(400, "Invalid supplier_id: %s" % supplier_id)

        supplier = Supplier.query.filter(Supplier.supplier_id == supplier_id) \
            .all()
        if not supplier:
            abort(404, "supplier_id '%d' not found" % supplier_id)

        items = services.filter(Service.supplier_id == supplier_id).all()
        return jsonify(
            services=[service.serialize() for service in items],
            links=dict()
        )

    services = services.paginate(
        page=page,
        per_page=current_app.config['DM_API_SERVICES_PAGE_SIZE'],
    )

    return jsonify(
        services=[service.serialize() for service in services.items],
        links=pagination_links(
            services,
            '.list_services',
            request.args
        )
    )


@main.route('/archived-services', methods=['GET'])
def list_archived_services_by_service_id():
    """
    Retrieves a list of services from the archived_services table
    for the supplied service_id
    :query_param service_id:
    :return: List[service]
    """

    is_valid_service_id_or_400(request.args.get("service-id", "no service id"))
    service_id = request.args.get("service-id", "no service id")

    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        abort(400, "Invalid page argument")

    services = ArchivedService.query.filter(Service.service_id == service_id)

    services = services.paginate(
        page=page,
        per_page=current_app.config['DM_API_SERVICES_PAGE_SIZE'],
    )

    if request.args and not services.items:
        abort(404)
    return jsonify(
        services=[service.serialize() for service in services.items],
        links=pagination_links(
            services,
            '.list_services',
            request.args
        )
    )


@main.route('/services/<string:service_id>', methods=['POST'])
def update_service(service_id):
    """
        Update a service. Looks service up in DB, and updates the JSON listing.
    """

    is_valid_service_id_or_400(service_id)

    service = Service.query.filter(
        Service.service_id == service_id
    ).first_or_404()

    service_to_archive = ArchivedService.from_service(service)

    db.session.add(
        update_and_validate_service(
            service,
            validate_and_return_service_request(service_id),
            validate_and_return_updater_request()
        )
    )
    db.session.add(service_to_archive)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        abort(400, e.orig)

    index_service(service)

    return jsonify(message="done"), 200


@main.route('/services/<string:service_id>', methods=['PUT'])
def import_service(service_id):
    """Import services from legacy digital marketplace

    This endpoint creates new services where we have an existing ID, it
    should not be used as a model for how we add new services.
    """
    is_valid_service_id_or_400(service_id)

    service = Service.query.filter(
        Service.service_id == service_id
    ).first()

    if service is not None:
        abort(400, "Cannot update service by PUT")

    now = datetime.utcnow()

    updater_json = validate_and_return_updater_request()
    service_json = validate_and_return_service_request(service_id)

    service_data = drop_foreign_fields(
        service_json,
        ['supplierName', 'links', 'frameworkName']
    )

    framework = detect_framework_or_400(service_data)
    service_data = drop_foreign_fields(service_data, ['id'])

    supplier_id = service_data.pop('supplierId')
    supplier = Supplier.query.filter(
        Supplier.supplier_id == supplier_id
    ).first()
    if supplier is None:
        abort(400, "Key (supplierId)=({}) is not present".format(supplier_id))

    framework = Framework.query.filter(
        Framework.name == framework
    ).first()

    service = Service(service_id=service_id)
    service.supplier_id = supplier_id
    service.framework_id = framework.id
    service.updated_at = now
    service.created_at = now
    service.status = service_data.pop('status', 'published')
    service.updated_by = updater_json['updated_by']
    service.updated_reason = updater_json['update_reason']
    service.data = service_data

    db.session.add(service)

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        abort(400, "Database Error: {0}".format(e))

    index_service(service)

    return jsonify(services=service.serialize()), 201


@main.route('/services/<string:service_id>', methods=['GET'])
def get_service(service_id):
    is_valid_service_id_or_400(service_id)

    service = Service.query.filter(
        Service.service_id == service_id) \
        .filter(Service.framework.has(Framework.expired == false())) \
        .first_or_404()

    return jsonify(services=service.serialize())


@main.route('/archived-services/<int:archived_service_id>', methods=['GET'])
def get_archived_service(archived_service_id):
    """
    Retrieves a service from the archived_service by PK
    :param archived_service_id:
    :return: service
    """

    service = ArchivedService.query.filter(
        ArchivedService.id == archived_service_id
    ).first_or_404()

    return jsonify(services=service.serialize())


@main.route(
    '/services/<string:service_id>/status/<string:status>',
    methods=['POST']
)
def update_service_status(service_id, status):
    """
    Updates the status parameter of a service, and archives the old one.
    :param service_id:
    :param status:
    :return: the newly updated service in the response
    """

    # Statuses are defined in the Supplier model
    valid_statuses = [
        "published",
        "enabled",
        "disabled"
    ]

    is_valid_service_id_or_400(service_id)

    service = Service.query.filter(
        Service.service_id == service_id
    ).first_or_404()

    service_to_archive = ArchivedService.from_service(service)
    update_json = validate_and_return_updater_request()

    if status not in valid_statuses:
        valid_statuses_single_quotes = display_list(
            ["\'{}\'".format(vstatus) for vstatus in valid_statuses]
        )
        abort(400, "\'{0}\' is not a valid status. "
                   "Valid statuses are {1}"
              .format(status, valid_statuses_single_quotes)
              )

    now = datetime.utcnow()
    prior_status = service.status
    service.status = status
    service.updated_at = now
    service.updated_by = update_json['updated_by']
    service.updated_reason = update_json['update_reason']

    db.session.add(service)
    db.session.add(service_to_archive)

    db.session.commit()

    if prior_status != status:

        # If it's being unpublished, delete it from the search api.
        if prior_status == 'published':
            delete_service_from_index(service)
        else:
            # If it's being published, index in the search api.
            index_service(service)

    return jsonify(services=service.serialize()), 200
