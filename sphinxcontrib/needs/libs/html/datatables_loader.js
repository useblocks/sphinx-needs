$(document).ready(function() {
    $('table.NEEDS_DATATABLES').DataTable( {
        dom: 'lBfrtip',
        colReorder: true,
        scrollX: true,
        autoWidth: false,
        buttons: [
            {
                extend: 'colvis',
                text: 'Columns'
            },
            'copy', 'excel', 'pdf'
        ],
        responsive: false
    });

} );
