// Wait for GridJS to load
function waitForGridJS() {
    return new Promise((resolve) => {
        if (window.gridjs) {
            resolve();
        } else {
            const checkGridJS = setInterval(() => {
                if (window.gridjs) {
                    clearInterval(checkGridJS);
                    resolve();
                }
            }, 100);
        }
    });
}

// Load GridJS and CSS
async function loadGridJSandJSPDF() {
    // Wait for GridJS to be available
    await waitForGridJS();

    // Wait for jsPDF and autoTable to be available
    await new Promise((resolve) => {
        if (window.jspdf) {
            resolve();
        } else {
            const checkJSPDF = setInterval(() => {
                if (window.jspdf) {
                    clearInterval(checkJSPDF);
                    resolve();
                }
            }, 100);
        }
    });
    await new Promise((resolve) => {
        if (window.autoTable) {
            resolve();
        } else {
            const checkAutoTable = setInterval(() => {
                if (window.autoTable) {
                    clearInterval(checkAutoTable);
                    resolve();
                }
            }, 100);
        }
    });
}


// Custom sorter function
function customGridJSSorter(a, b) {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = a;
    const aVal = tempDiv.textContent ? String(tempDiv.textContent).toLowerCase() : null;
    tempDiv.innerHTML = b;
    const bVal = tempDiv.textContent ? String(tempDiv.textContent).toLowerCase() : null;

    // Handle empty values
    if (!aVal && !bVal) return 0;
    if (!aVal) return -1;
    if (!bVal) return 1;

    // Use localeCompare for proper string comparison
    return aVal.localeCompare(bVal, undefined, {
        numeric: true,
        sensitivity: 'base'
    });
}


// CSV Export function
function exportToCSV(tableId, headers, rows) {
    const filename = `${tableId}-export`;
    const csv = [
        headers.join(","),
        ...rows.map(row => row.map(field => `"${field}"`).join(","))
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename + ".csv";
    link.click();
}

// PDF Export function
function exportToPDF(tableId, headers, rows) {
    const filename = `${tableId}-export`;
    const doc = new jspdf.jsPDF({
        orientation: 'landscape', 
        unit: 'mm',
        format: 'letter',
        putOnlyUsedFonts: true,
    });

    autoTable(doc, {
        head: [headers],
        body: rows,
        tableLineColor: [0, 0, 0],
        tableLineWidth: 0.15,
        theme: 'plain',
        styles: {
            fontSize: 10,
            cellPadding: 2,
            lineHeight: 1.5,
            halign: 'left',
            valign: 'middle',
            overflow: 'linebreak',
            cellWidth: 'auto',
            lineColor: [0, 0, 0],
            lineWidth: 0.15
        },
        headerStyles: {
            fontSize: 14,
            fontStyle: 'bold'
        },
        bodyStyles: {
            fillColor: false,
            textColor: 0
        },
        alternateRowStyles: {
            overflow: 'linebreak',
            cellWidth: 'auto',
        },
        columnStyles: headers.reduce((acc, _, index) => {
            acc[index] = { cellWidth: 'auto', overflow: 'linebreak' };
            return acc;
        }, {}),
        margin: { top: 10, right: 10, bottom: 10, left: 10 },
        didParseCell: function(data) {
            data.cell.styles.cellWidth = 'wrap';
            data.cell.styles.overflow = 'linebreak';
        }
    });
    doc.save(filename + ".pdf");
}

function addDownloadButtons(tableId, headers, rows) {
    const downloadBtns = document.createElement('div');
    const csvDownloadBtns = document.createElement('button');
    const pdfDownloadBtns = document.createElement('button');

    csvDownloadBtns.id = `${tableId}-download-csv`;
    pdfDownloadBtns.id = `${tableId}-download-pdf`;
    csvDownloadBtns.textContent = "Download CSV";
    pdfDownloadBtns.textContent = "Download PDF";
    downloadBtns.appendChild(csvDownloadBtns);
    downloadBtns.appendChild(pdfDownloadBtns);
    downloadBtns.id = `${tableId}-download-btns`;
    downloadBtns.className = 'gridjs-download-btns';
    downloadBtns.style.float = 'right';

    const headerNames = headers.map(header => header.name);
    const textRows = rows.map(row => 
        row.map(cell => {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = cell;
        return tempDiv.textContent.trim();
        })
    );

    csvDownloadBtns.onclick = () => exportToCSV(tableId, headerNames, textRows);
    pdfDownloadBtns.onclick = () => exportToPDF(tableId, headerNames, textRows);

    const gridJSHeadDiv = document.querySelector(`#gridjs-wrapper-${tableId} .gridjs-head`);
    if (gridJSHeadDiv) {
        gridJSHeadDiv.appendChild(downloadBtns);
    }
}

async function initializeGridJS() {
    await loadGridJSandJSPDF();
    
    document.querySelectorAll('table.NEEDS_DATATABLES').forEach(table => {
        const tableId = (table.id?.replace(/[^a-zA-Z0-9_-]/g, '_') || `gridjs-table-${Math.random().toString(36).substring(2, 11)}`);
        const wrapper = document.createElement('div');
        wrapper.className = 'gridjs-needs-table';
        wrapper.id = `gridjs-wrapper-${tableId}`;

        table.insertAdjacentElement('beforebegin', wrapper);

        const headers = Array.from(table.querySelectorAll('th')).map(th => ({
            id: `${tableId}_${th.textContent.trim().toLowerCase().replace(/\s+/g, '-')}`,
            name: th.textContent.trim(),
            formatter: (cell) => gridjs.html(cell),
            sort: {
                compare: (a, b) => customGridJSSorter(a, b)
            }
        }));

        const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr => 
            Array.from(tr.querySelectorAll('td')).map(td => td.innerHTML.trim())
        );

        // Create and render Grid.js instance
        const gridInstance = new gridjs.Grid({
            columns: headers,
            data: rows,
            width: '100%',
            height: '500px',
            sort: true,
            search: true,
            resizable: true,
            fixedHeader: true,
            pagination: {
                enabled: true,
                limit: 10
            },
            className: {
                table: table.className,
            },
            style: {
                table: {width: '100%', height: '500px', display: 'table'},
            },
            language: {
                'search': {
                    'placeholder': '🔍 Search...'
                },
                'pagination': {
                    'previous': '⬅️ Previous',
                    'next': '➡️ Next',
                    'showing': '😃 Displaying',
                    'results': () => 'rows'
                }
            },
        });

        gridInstance.render(wrapper);

        setTimeout(() => {
            addDownloadButtons(tableId, headers, rows);
        }, 100);

        // Remove the original table
        table.remove();
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeGridJS);
} else {
    initializeGridJS();
}
