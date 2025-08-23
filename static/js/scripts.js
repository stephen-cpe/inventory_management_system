// JavaScript functions for the Church Inventory System

// Utility function to get current time
function getCurrentTime() {
    return new Date().toLocaleTimeString();
}

// Delete item page functionality
function initializeDeleteItemPage() {
    const checkbox = document.getElementById('confirmDelete');
    const deleteBtn = document.getElementById('deleteButton');
    const form = document.getElementById('deleteForm');
    
    if (checkbox && deleteBtn) {
        console.log('Delete page elements found');
        console.log('Initial checkbox state:', checkbox.checked);
        console.log('Initial button disabled state:', deleteBtn.disabled);
        console.log('Checkbox value:', checkbox.value);
        
        checkbox.addEventListener('change', function() {
            deleteBtn.disabled = !this.checked;
            console.log('Checkbox changed, delete button disabled:', !this.checked);
            console.log('Checkbox checked:', this.checked);
            console.log('Button disabled after change:', deleteBtn.disabled);
            console.log('Checkbox value:', this.value);
        });
        
        // Set initial state based on checkbox state
        deleteBtn.disabled = !checkbox.checked;
        console.log('Initial button disabled state set to:', !checkbox.checked);
    }
    
    // Handle form submission - ONLY for debugging, don't prevent default
    if (form) {
        form.addEventListener('submit', function(e) {
            console.log('Delete form submission event triggered');
            console.log('Checkbox state at submit:', checkbox ? checkbox.checked : 'no checkbox');
            console.log('Checkbox value at submit:', checkbox ? checkbox.value : 'no checkbox');
            console.log('Form data being submitted:');
            
            // Log form data
            const formData = new FormData(form);
            for (let [key, value] of formData.entries()) {
                console.log(key, value);
            }
            
            // DO NOT prevent default - let the form submit normally
            console.log('Form will submit normally');
        });
    }
}

// Disposal form functionality
function initializeDisposalForm() {
    try {
        console.log('Initializing disposal form');
        
        // Quantity validation logic
        function updateQuantityMax(selectElement) {
            // Check if selectElement and its options are valid
            if (!selectElement || !selectElement.options || selectElement.selectedIndex < 0) {
                console.log('Invalid select element or no option selected');
                return;
            }
            
            const selectedOption = selectElement.options[selectElement.selectedIndex];
            if (!selectedOption) {
                console.log('No selected option found');
                return;
            }
            
            const quantityInput = selectElement.closest('.disposal-entry').querySelector('input[name="quantity"]');
            if (!quantityInput) {
                console.log('No quantity input found');
                return;
            }
            
            const maxQty = parseInt(selectedOption.dataset.max || 0);
            console.log('Setting max quantity to:', maxQty);
            
            quantityInput.max = maxQty;
            quantityInput.setCustomValidity(
                maxQty === 0 ? 'No quantity available in this location' : ''
            );
            
            if(quantityInput.value > maxQty) {
                quantityInput.value = maxQty;
            }
        }

        // Initialize all selects on load
        const locationSelects = document.querySelectorAll('select[name="location"]');
        console.log('Found location selects:', locationSelects.length);
        locationSelects.forEach(select => {
            try {
                console.log('Processing select:', select);
                if(select.value) {
                    console.log('Select has value, updating quantity max');
                    updateQuantityMax(select);
                }
            } catch (e) {
                console.error('Error processing select:', e);
            }
        });

        // Update on location change
        const disposalEntries = document.getElementById('disposalEntries');
        console.log('Disposal entries element:', disposalEntries);
        if (disposalEntries) {
            disposalEntries.addEventListener('change', function(e) {
                try {
                    console.log('Change event detected:', e.target.name);
                    if (e.target.name === 'location') {
                        console.log('Location changed, updating quantity max');
                        updateQuantityMax(e.target);
                    }
                } catch (e) {
                    console.error('Error in change event handler:', e);
                }
            });
        } else {
            console.log('Disposal entries element not found');
        }
    } catch (e) {
        console.error('Error initializing disposal form:', e);
    }
}

// Initialize functions based on the current page
document.addEventListener('DOMContentLoaded', function() {
    console.log("Church Inventory System - JavaScript loaded successfully!");
    
    // Check if we're on the delete item page
    const deleteForm = document.getElementById('deleteForm');
    console.log('Delete form found:', !!deleteForm);
    if (deleteForm) {
        console.log("Initializing delete item page");
        initializeDeleteItemPage();
    }
    
    // Check if we're on the disposal form page
    const disposalForm = document.getElementById('disposalForm');
    console.log('Disposal form found:', !!disposalForm);
    if (disposalForm) {
        console.log("Initializing disposal form page");
        initializeDisposalForm();
    }
});