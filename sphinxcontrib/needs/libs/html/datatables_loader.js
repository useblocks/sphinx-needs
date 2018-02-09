$(document).ready(function() {
    $('table.docutils').DataTable();
} );

// Code if more than one jquery lib would be available
// $(document).ready(function() {
//     jquery_datatable = jQuery.noConflict(true);
//     jquery_datatable('table.docutils').DataTable();
//
//     alert("active:" + $.fn.jquery)
//     alert("behind:" + jquery_datatable.fn.jquery)
// } );

