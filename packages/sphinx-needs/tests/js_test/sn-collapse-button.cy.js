describe('Test Sphinx Needs Collapse', () => {
  it('Visit Sphinx Needs Homepage', () => {
    // 1. Given a user visits http://localhost:65323/
    cy.visit('/')

    cy.get('table.need span.needs.needs_collapse').each(($el, index, $list) => {
    // 2. When page loads, select all elements that matches the selector `table.need span.needs.needs_collapse`

        var id = $el.attr("id");
        var parts = id.split("__");
        var rows = parts.slice(2);

        var table = $el.closest('table');
        var need_table_id = table.closest("div[id^=SNCB-]").attr("id");

        // 3. Check if the id of the element contains show or hide
        if (parts[1] == "show") {
            cy.get($el).within(() => {
              // 4. Then check if `span.needs.visible` has the class `collapse_is_hidden`
              cy.get('span.needs.visible').should('have.class', 'collapse_is_hidden')
            })
        } else {
            cy.get($el).within(() => {
              // 4. Then check if `span.needs.collapse` has the class `collapse_is_hidden`
              cy.get('span.needs.collapsed').should('have.class', 'collapse_is_hidden')
            })

            for (var row in rows) {
                // 5. And check if `#${need_table_id} table tr.${rows[row]}` has the class `collapse_is_hidden`
                cy.get(`#${need_table_id} table tr.${rows[row]}`).should('have.class', 'collapse_is_hidden')
            }
        }
    })
  })
})

describe('Test Sphinx Needs Collapse Click', () => {
  it('Visit Sphinx Needs Directive page', () => {
    // 1. Given a user visits http://localhost:65323/
    cy.visit('/')

    cy.get('table.need span.needs.needs_collapse').each(($el, index, $list) => {
    // 2. When page loads, select all elements that matches the selector `table.need span.needs.needs_collapse`

        var id = $el.attr("id");
        var parts = id.split("__");
        var rows = parts.slice(2);

        var table = $el.closest('table');
        var need_table_id = table.closest("div[id^=SNCB-]").attr("id");

        if (parts[1] == "show") {
            // 3. Click collapse/expand button
            cy.get($el).click()

            for (var row in rows) {
                // 4. And check if `#${need_table_id} table tr.${rows[row]}` has the class `collapse_is_hidden`
                cy.get(`#${need_table_id} table tr.${rows[row]}`).should('have.class', 'collapse_is_hidden')
            }

            cy.get($el).within(() => {
                  // 5. Then check if `span.needs.collapse` has the class `collapse_is_hidden`
                  cy.get('span.needs.collapsed').should('have.class', 'collapse_is_hidden')
                  // 6. And check if `span.needs.visible` has the class `collapse_is_hidden`
                  cy.get('span.needs.visible').should('not.have.class', 'collapse_is_hidden')
                })
        } else{
            // 3. Click collapse/expand button
            cy.get($el).click()

            for (var row in rows) {
                // 4. And check if `#${need_table_id} table tr.${rows[row]}` has the class `collapse_is_hidden`
                cy.get(`#${need_table_id} table tr.${rows[row]}`).should('not.have.class', 'collapse_is_hidden')
            }

            cy.get($el).within(() => {
                  // 5. Then check if `span.needs.collapse` has the class `collapse_is_hidden`
                  cy.get('span.needs.collapsed').should('not.have.class', 'collapse_is_hidden')
                  // 6. Check if `span.needs.visible` has the class `collapse_is_hidden`
                  cy.get('span.needs.visible').should('have.class', 'collapse_is_hidden')
                })
        }

    })
  })
})