document.addEventListener('DOMContentLoaded', function() {

    function requireOneEntryOnManyToManyField(form_id, inline_form_id, fields, error_msg) {
        const form = document.getElementById(form_id);
        if (!form) return;

        form.addEventListener('submit', function(e) {
            let inlineFormFilled = false;
            const totalForms = document.getElementById(`id_${inline_form_id}_set-TOTAL_FORMS`).value;

            for (let i = 0; i < totalForms; i++) {
                let numFieldsFilled = 0;
                for (let field_name of fields) {
                    const field = document.getElementById(`id_${inline_form_id}_set-${i}-${field_name}`);
                    if (field && field.value) {
                        numFieldsFilled++;
                    }
                }
                if (numFieldsFilled === fields.length) {
                    inlineFormFilled = true;
                    break;
                }
            }

            if (!inlineFormFilled) {
                e.preventDefault();
                alert(error_msg);
            }
        });
    }

    requireOneEntryOnManyToManyField(
        'compliancestandard_form',
        'compliancestandardReference',
        ['text', 'url'],
        'Please add at least one Compliance Standard Reference'
    );

    requireOneEntryOnManyToManyField(
        'compliancestandardrule_form',
        'compliancestandardrulecondition',
        ['code_type', 'operator'],
        'Please add at least one Compliance Standard Rule Condition'
    );
});
