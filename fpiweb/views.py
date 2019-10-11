"""
views.py - establish the views (pages) for the F. P. I. web application.
"""
from io import BytesIO
from json import loads
from logging import getLogger, debug
from string import digits

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.serializers import serialize
from django.db.models import Max
from django.forms import modelformset_factory
from django.http import FileResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, \
    CreateView, UpdateView, DeleteView, FormView


from fpiweb.code_reader import \
    CodeReaderError, \
    read_box_number
from fpiweb.forms import \
    BoxItemForm, \
    BuildPalletForm, \
    ConstraintsForm, \
    LoginForm, \
    NewBoxForm, \
    PrintLabelsForm
from fpiweb.models import \
    Action, \
    Box, \
    BoxNumber, \
    Constraints
from fpiweb.qr_code_utilities import QRCodePrinter

__author__ = '(Multiple)'
__project__ = "Food-Pantry-Inventory"
__creation_date__ = "04/01/2019"


logger = getLogger('fpiweb')


def error_page(
        request,
        message=None,
        message_list=tuple(),
        status=400):
    return render(
        request,
        'fpiweb/error.html',
        {
            'message': message,
            'message_list': message_list,
        },
        status=status
    )


class IndexView(TemplateView):
    """
    Default web page (/index)
    """
    template_name = 'fpiweb/index.html'


class AboutView(TemplateView):
    """
    The About View for this application.
    """
    template_name = 'fpiweb/about.html'
    mycontext = dict()
    mycontext['project_type'] = 'open source'
    extra_context = mycontext


class LoginView(FormView):
    template_name = 'fpiweb/login.html'
    form_class = LoginForm
    success_url = reverse_lazy('fpiweb:index')

    def form_valid(self, form):
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')

        user = authenticate(self.request, username=username, password=password)

        if user is None:
            form.add_error(None, "Invalid username and/or password")
            return self.form_invalid(form)

        login(self.request, user)
        return super().form_valid(form)


class LogoutView(TemplateView):
    template_name = 'fpiweb/logout.html'

    def get_context_data(self, **kwargs):

        logout(self.request)
        nothing = dict()
        return nothing


class ConstraintsListView(LoginRequiredMixin, ListView):
    """
    List of existing constraints.
    """
    model = Constraints
    template_name = 'fpiweb/constraints_list.html'
    context_object_name = 'constraints_list_content'

    def get_context_data(self, *, object_list=None, **kwargs):
        """
        Add additional content to the context dictionary.

        :param object_list:
        :param kwargs:
        :return:
        """
        context = super(ConstraintsListView, self).get_context_data()

        # provide additional information to the template
        INT_RANGE = Constraints.INT_RANGE
        CHAR_RANGE = Constraints.CHAR_RANGE
        range_list = [INT_RANGE, CHAR_RANGE]
        context['range_list'] = range_list

        return context


class ConstraintCreateView(LoginRequiredMixin, CreateView):
    """
    Create an animal or daily quest using a generic CreateView.
    """
    model = Constraints
    template_name = 'fpiweb/constraint_edit.html'
    context_object_name = 'constraint_edit_context'

    formClass = ConstraintsForm

    # TODO Why are fields required here in the create - 1/18/17
    fields = ['constraint_name', 'constraint_descr', 'constraint_type',
              'constraint_min', 'constraint_max', 'constraint_list', ]

    def get_context_data(self, **kwargs):
        """
        Modify the context before rendering the template.

        :param kwargs:
        :return:
        """

        context = super(ConstraintCreateView, self).get_context_data(**kwargs)
        context['action'] = reverse('fpiweb:constraint_new')
        return context

    def get_success_url(self):
        """
        Run once form is successfully validated.

        :return:
        """
        results = reverse('fpiweb:constraints_view')
        return results


class ConstraintUpdateView(LoginRequiredMixin, UpdateView):
    """
    Update an animal or daily quest using a generic UpdateView.
    """

    model = Constraints
    template_name = 'fpiweb/constraint_edit.html'
    context_object_name = 'constraint_edit_context/'

    form_class = ConstraintsForm

    # TODO Why are fields forbidden here in the update - 1/18/17
    # fields = ['category', 'constraints_order', 'constraints_name',
    # 'date_started', ]

    def get_context_data(self, **kwargs):
        """
        Modify the context before rendering the template.

        :param kwargs:
        :return:
        """

        context = super(ConstraintUpdateView, self).get_context_data(**kwargs)
        context['action'] = reverse('fpiweb:constraint_update',
                                    kwargs={'pk': self.get_object().id})
        return context

    def get_success_url(self):
        """
        Set the next URL to use once the edit is successful.
        :return:
        """

        results = reverse('fpiweb:constraints_view')
        return results


class ConstraintDeleteView(LoginRequiredMixin, DeleteView):
    """
    Delete an animal or daily quest using a generic DeleteView.
    """
    model = Constraints
    template_name = 'fpiweb/constraint_delete.html'
    context_object_name = 'constraint_delete_context'

    def get_success_url(self):
        """
        Set the next URL to use once the delete is successful.
        :return:
        """

        results = reverse('fpiweb:constraints_view')
        return results


class BoxNewView(LoginRequiredMixin, View):
    # model = Box
    template_name = 'fpiweb/box_new.html'
    # context_object_name = 'box'
    # form_class = NewBoxForm

    # def get_success_url(self):
    #     return reverse(
    #         'fpiweb:box_details',
    #         args=(self.object.pk,)
    #     )

    def get(self, request, *args, **kwargs):
        box_number = kwargs.get('box_number')
        if not box_number:
            return error_page(request, 'missing box_number')

        if not BoxNumber.validate(box_number):
            return error_page(
                request,
                "Invalid box_number '{}'".format(box_number),
            )

        new_box_form = NewBoxForm(initial={'box_number': box_number})
        return render(
            request,
            self.template_name,
            {
                'form': new_box_form,
            }
        )

    def post(self, request, *args, **kwargs):
        box_number = kwargs.get('box_number')
        if not box_number:
            return error_page(request, 'missing box_number')

        if not BoxNumber.validate(box_number):
            return error_page(
                request,
                "Invalid box_number '{}'".format(box_number),
            )

        new_box_form = NewBoxForm(
            request.POST,
            initial={'box_number': box_number},
        )

        if not new_box_form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    'form': new_box_form,
                },
            )

        box = new_box_form.save()

        action = request.session.get('action')
        if action == Action.ACTION_BUILD_PALLET:
            return redirect(
                reverse(
                    'fpiweb:build_pallet_add_box',
                    args=(box.pk,)
                )
            )

        return redirect(reverse('fpiweb:box_details', args=(box.pk,)))


class BoxEditView(LoginRequiredMixin, UpdateView):
    model = Box
    template_name = 'fpiweb/box_edit.html'
    context_object_name = 'box'
    form_class = NewBoxForm
    success_url = reverse_lazy('fpiweb:index')


class BoxDetailsView(LoginRequiredMixin, DetailView):

    model = Box
    template_name = 'fpiweb/box_detail.html'
    context_object_name = 'box'

    def get_context_data(self, **kwargs):
        debug(f"kwargs are {kwargs}")
        context = super().get_context_data(**kwargs)
        return context


class BoxEmptyMoveView(LoginRequiredMixin, TemplateView):
    template_name = 'fpiweb/box_empty_move.html'

    def get_context_data(self, **kwargs):
        return {}


class BoxMoveView(LoginRequiredMixin, TemplateView):
    template_name = 'fpiweb/box_empty_move.html'

    def get_context_data(self, **kwargs):
        return {}


class BoxEmptyView(LoginRequiredMixin, View):
    pass


class BoxScannedView(LoginRequiredMixin, View):

    def get(self, request, **kwargs):
        box_number = kwargs.get('number')
        if box_number is None:
            return error_page(request, "missing kwargs['number']")
        box_number = BoxNumber.format_box_number(box_number)

        action = request.session.get('action')

        if action != Action.ACTION_BUILD_PALLET:
            return error_page(
                request,
                "What to do when action is {}?".format(action)
            )

        try:
            box = Box.objects.get(box_number=box_number)
        except Box.DoesNotExist:
            return redirect('fpiweb:box_new', box_number=box_number)

        return redirect('fpiweb:build_pallet', args=(box.pk,))


class TestScanView(LoginRequiredMixin, TemplateView):

    template_name = 'fpiweb/test_scan.html'

    @staticmethod
    def get_box_scanned_url(box_number):
        if box_number.lower().startswith('box'):
            box_number = box_number[3:]
        return reverse('fpiweb:box_scanned', args=(box_number,))

    @staticmethod
    def get_box_url_by_filters(**filters):
        box_number = Box.objects \
            .filter(**filters) \
            .values_list('box_number', flat=True) \
            .first()
        if box_number is None:
            return ""
        return TestScanView.get_box_scanned_url(box_number)

    def get_context_data(self, **kwargs):

        full_box_url = self.get_box_url_by_filters(product__isnull=False)
        empty_box_url = self.get_box_url_by_filters(product__isnull=True)

        new_box_url = self.get_box_scanned_url(
            BoxNumber.get_next_box_number()
        )

        # schema http or https
        schema = 'http'
        if settings.DEBUG == False and hasattr(self.request, 'schema'):
            schema = self.request.schema

        protocol_and_host = "{}://{}".format(
            schema,
            self.request.META.get('HTTP_HOST', '')
        )

        full_box_url = protocol_and_host + full_box_url
        empty_box_url = protocol_and_host + empty_box_url
        new_box_url = protocol_and_host + new_box_url

        empty_box = Box.objects.filter(product__isnull=True).first()
        full_box = Box.objects.filter(product__isnull=False).first()

        return {
            'full_box_url': full_box_url,
            'empty_box_url': empty_box_url,
            'new_box_url': new_box_url,
            'empty_box': empty_box,
            'full_box': full_box,
            'next_box_number': BoxNumber.get_next_box_number(),
        }


class BuildPalletView(View):
    """Set action in view"""
    template_name = 'fpiweb/build_pallet.html'

    BoxFormFactory = modelformset_factory(
        Box,
        form=BoxItemForm,
        extra=1,
    )

    def get(self, request, *args, **kwargs):

        request.session['action'] = Action.ACTION_BUILD_PALLET

        box_pk = kwargs.get('box_pk')

        build_pallet_form = BuildPalletForm()

        kwargs = {
            'prefix': 'box_forms',
        }
        if box_pk:
            kwargs['queryset'] = Box.objects.filter(pk=box_pk)
        else:
            kwargs['queryset'] = Box.objects.none()

        box_forms = self.BoxFormFactory(**kwargs)

        context = {
            'form': build_pallet_form,
            'box_forms': box_forms,
        }
        return render(request, self.template_name, context)

    def post(self, request):

        form = BuildPalletForm(request.POST)
        box_forms = self.BoxFormFactory(request.POST, prefix='box_forms')

        if box_forms:
            box_form = box_forms[0]
            print(dir(box_form))

        if not form.is_valid() or not box_forms.is_valid():
            return render(
                request,
                self.template_name,
                {
                    'form': form,
                    'box_forms': box_forms,
                }
            )

        return error_page(request, "forms are valid")


class ScannerViewError(RuntimeError):
    pass


class ScannerView(View):

    @staticmethod
    def response(success, data=None, errors=None, status=200):
        return JsonResponse(
            {
                'success': success,
                'data': data if data else {},
                'errors': errors if errors else [],
            },
            status=status
        )

    @staticmethod
    def error_response(errors, status=400):
        return ScannerView.response(
            False,
            errors,
            status=status
        )

    @staticmethod
    def get_keyed_in_box_number(box_number):
        """
        :param box_number: the box number (a string), may be None
        :return:
        """
        box_number = box_number or ''
        if not box_number:
            return None

        # strip out everything, but digits
        box_number = "".join(c for c in box_number if c in digits)
        if not box_number:
            return None

        try:
            box_number = int(box_number)
        except ValueError:
            return None

        return BoxNumber.format_box_number(box_number)

    @staticmethod
    def get_box(scan_data=None, box_number=None):
        if not scan_data and not box_number:
            raise ScannerViewError('missing scan_data and box_number')

        if not box_number:
            try:
                box_number = read_box_number(scan_data)
            except CodeReaderError as cre:
                raise ScannerViewError(str(cre))

        default_box_type = Box.box_type_default()

        box, created = Box.objects.get_or_create(
            box_number=box_number,
            defaults={
                'box_type': default_box_type,
                'quantity': default_box_type.box_type_qty,
            }
        )
        return box, created

    @staticmethod
    def get_box_data(scan_data=None, box_number=None):

        box, created = ScannerView.get_box(
            scan_data=scan_data,
            box_number=box_number
        )

        # serialize works on an iterable of objects and returns a string
        # loads returns a list of dicts
        box_dicts = loads(serialize("json", [box]))

        data = {
            'box': box_dicts[0],
            'box_meta': {
                'is_new': created,
            }
        }
        return data

    def post(self, request, *args, **kwargs):

        scan_data = request.POST.get('scanData')
        box_number = self.get_keyed_in_box_number(
            request.POST.get('boxNumber'),
        )

        try:
            box_data = self.get_box_data(scan_data, box_number)
        except ScannerViewError as sve:
            error_message = str(sve)
            logger.error(error_message)
            return self.error_response([error_message])

        return self.response(True, data=box_data, status=200)


class PrintLabelsView(View):

    template_name = 'fpiweb/print_labels.html'

    @staticmethod
    def get_base_url(meta):
        protocol = meta.get('SERVER_PROTOCOL', 'HTTP/1.1')
        protocol = protocol.split('/')[0].lower()

        host = meta.get('HTTP_HOST')
        return f"{protocol}://{host}/"

    def get(self, request, *args, **kwargs):
        max_box_number = Box.objects.aggregate(Max('box_number'))
        print("max_box_number", max_box_number)

        return render(
            request,
            self.template_name,
            {'form': PrintLabelsForm()}
        )

    def post(self, request, *args, **kwargs):
        base_url = self.get_base_url(request.META)

        form = PrintLabelsForm(request.POST)
        if not form.is_valid():
            print("form invalid")
            return render(
                request,
                self.template_name,
                {'form': form},
            )
        print("form valid")

        buffer = BytesIO()

        QRCodePrinter().print(
            form.cleaned_data.get('starting_number'),
            form.cleaned_data.get('number_to_print'),
            buffer,
        )

        # FileResponse sets the Content-Disposition header so that browsers
        # present the option to save the file.
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename='labels.pdf')


class BoxItemFormView(LoginRequiredMixin, View):

    template_name = 'fpiweb/box_form.html'

    @staticmethod
    def get_form(box, prefix=None):
        kwargs = {'instance': box}
        if prefix:
            kwargs['prefix'] = prefix
        form = BoxItemForm(**kwargs)
        return form

    def post(self, request):

        scan_data = request.POST.get('scanData')
        box_number = ScannerView.get_keyed_in_box_number(
            request.POST.get('boxNumber'),
        )
        prefix = request.POST.get('prefix')
        box, created = ScannerView.get_box(scan_data, box_number)

        return render(
            request,
            self.template_name,
            {
                'form': self.get_form(box, prefix),
            },
        )


# EOF
