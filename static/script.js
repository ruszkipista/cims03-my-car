// inspired by https://stackoverflow.com/questions/59566549/how-to-do-delete-confirmation-for-a-table-data-with-bootstrap-modal-in-django
document.addEventListener('DOMContentLoaded', () => {
    const sources = document.querySelectorAll('[data-mdb-toggle="modal"]')
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
                .then(result=>{
                // call the redirected URL
                document.location.href=result.url;
                }); 
            });
            }
        });
    });
});