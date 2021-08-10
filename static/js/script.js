// inspired by https://stackoverflow.com/questions/59566549/how-to-do-delete-confirmation-for-a-table-data-with-bootstrap-modal-in-django
document.addEventListener('DOMContentLoaded', connectModal());
function connectModal() {
    const sources = document.querySelectorAll('a[data-mdb-toggle="modal"]')
    sources.forEach(source => {
        source.addEventListener("click", event => {
            // extract target modal from attribute data-mdb-target
            const targetModal = document.querySelector(source.dataset.mdbTarget);
            if (targetModal) {
                // get the Button element with formMethod attribute
                const targetButton = targetModal.querySelector('button[formMethod]');
                targetButton.formAction = source.href;
                targetButton.addEventListener('click', (event) => {
                    fetch(event.target.formAction, {method:event.target.formMethod})
                    // learnt handling the returned whole page here https://gomakethings.com/getting-html-with-fetch-in-vanilla-js/
                    .then(result=> result.text())
                    .then(html => document.querySelector('html').innerHTML = html)
                    .then(_ => connectModal()); 
                });
            }
        });
    });
}

function selectTableRows(event){
    const select = event.currentTarget;
    
    const selectFilters = document.querySelectorAll('select[data-filter]');
    const trFilters = document.querySelectorAll('tr[data-filter]');
    trFilters.forEach(tr=>{
        let is_selected = true;
        selectFilters.forEach(e=>{
            let selectedOption = e.options[e.selectedIndex].value
            let rowValue = tr.dataset[e.id]
            is_selected &&= selectedOption=="" || rowValue == selectedOption; 
        })
        tr.style.display = (is_selected) ? "" : "none";
    })
}